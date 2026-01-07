#!/usr/bin/env python3
"""
微信公众号文章 Markdown → HTML 转换器 (增强版)

功能：
1. [Image Gen] 自动识别 `![Image](描述)`，通过 Gemini API (Nano Banana Pro) 生成配图
2. [Format] Markdown 转 HTML (微信风格)
3. [Calibration] 代码校准与清理

依赖:
    uv sync
    请在 .env 中配置 GOOGLE_API_KEY
"""

import argparse
import base64
import logging
import mimetypes
import os
import re
import time
from pathlib import Path

# 第三方库
import markdown
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# New GenAI SDK
from google import genai
from google.genai import types

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("WeChatGen")

# 加载环境变量
load_dotenv()

# ============================================
# Core Configuration
# ============================================

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Model Configuration
IMG_MODEL_NAME = os.getenv("IMG_MODEL_NAME", "gemini-3-pro-image-preview")
TEXT_MODEL_NAME = os.getenv("TEXT_MODEL_NAME", "gemini-3-pro-preview")

# Image Generation Settings (from .env)
# IMAGE_RESOLUTION: 1k, 2k, 4k (default: 2k)
# ENABLE_SEARCH: true/false (default: false)
IMAGE_RESOLUTION = os.getenv("IMAGE_RESOLUTION", "2k").lower()
ENABLE_SEARCH = os.getenv("ENABLE_SEARCH", "false").lower() == "true"

# Initialize Client
client = None
if GOOGLE_API_KEY:
    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
    except Exception as e:
        logger.error(f"GenAI Client 初始化失败: {e}")
else:
    logger.warning("未检测到 GOOGLE_API_KEY，图片生成功能将被跳过。")

# ============================================
# Image Generation Module
# ============================================

def expand_prompt(description: str) -> str:
    """使用 LLM 将简短描述扩展为详细的绘图 Prompt"""
    if not client:
        return description

    try:
        # 针对文章插图优化的 System Prompt
        sys_prompt = """
        你是一个专业的 AI 绘画提示词专家。请根据以下简单的画面描述，扩写成一段详细的英文绘图 Prompt。
        要求:
        1. 风格: 现代极简主义插画，平面风格，柔和暖色调(Morandi colors)，适合微信公众号配图。
        2. 画面: 构图简洁，留白适度，避免过于复杂的细节。
        3. 仅输出英文 Prompt，不要包含其他解释。
        """
        
        response = client.models.generate_content(
            model=TEXT_MODEL_NAME,
            contents=f"{sys_prompt}\n\n原始描述: {description}"
        )
        
        expanded = response.text.strip()
        logger.info(f"Prompt 优化: '{description}' -> '{expanded[:50]}...'")
        return expanded
    except Exception as e:
        logger.error(f"Prompt 扩展失败: {e}")
        return description

def generate_image_from_prompt(prompt: str, output_path: Path) -> bool:
    """
    调用 Gemini 生成图片
    配置从环境变量读取:
        IMAGE_RESOLUTION: '1k', '2k', '4k'
        ENABLE_SEARCH: 是否开启 Google Search Grounding
    """
    if not client:
        return False

    try:
        logger.info(f"正在调用 {IMG_MODEL_NAME} 生成图片 (Res: {IMAGE_RESOLUTION}, Search: {ENABLE_SEARCH})...")
        
        # 1. 配置分辨率 (currently unused per user's correction, kept for reference)
        res_map = {
            "1k": types.MediaResolution.MEDIA_RESOLUTION_LOW,
            "2k": types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
            "4k": types.MediaResolution.MEDIA_RESOLUTION_HIGH
        }
        # selected_res = res_map.get(IMAGE_RESOLUTION, types.MediaResolution.MEDIA_RESOLUTION_MEDIUM)

        # 2. 配置工具 (Search)
        tools = []
        if ENABLE_SEARCH:
            tools.append(types.Tool(google_search=types.GoogleSearch()))

        # 3. 构造 Prompt
        # 4. 调用 API
        # Note: media_resolution is for input processing, not generation output
        generation_config = types.GenerateContentConfig(
            tools=tools if tools else None
        )

        response = client.models.generate_content(
            model=IMG_MODEL_NAME,
            contents=f"Generate an image of: {prompt}",
            config=generation_config
        )
        
        # 5. 提取图片
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    output_path.write_bytes(part.inline_data.data)
                    logger.info(f"图片已保存: {output_path}")
                    return True
        
        logger.error("Gemini 生成响应中没有图片数据")
        return False

    except Exception as e:
        logger.error(f"图片生成 API 错误: {e}")
        return False

def image_to_base64(image_path: Path) -> str:
    """将图片文件转换为 base64 data URI"""
    mime_type, _ = mimetypes.guess_type(str(image_path))
    if not mime_type:
        mime_type = "image/png"
    
    with open(image_path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("utf-8")
    
    return f"data:{mime_type};base64,{b64_data}"


def process_images(content: str, assets_dir: Path) -> str:
    """
    扫描 Markdown 中的图片占位符 `![Image](描述)`
    配置从环境变量读取 (IMAGE_RESOLUTION, ENABLE_SEARCH)
    """
    pattern = r'!\[Image\]\((.*?)\)'
    
    matches = re.finditer(pattern, content, re.IGNORECASE)
    
    replacements = []
    
    for match in matches:
        desc = match.group(1)
        logger.info(f"发现待生成图片: {desc}")
        
        # 1. 扩展 Prompt (Gemini 3 Pro Text)
        full_prompt = expand_prompt(desc)
        
        # 2. 生成图片
        timestamp = int(time.time() * 1000)
        img_filename = f"gen_{timestamp}.png"
        img_path = assets_dir / img_filename
        
        # 3. 调用生成 (使用全局配置)
        success = generate_image_from_prompt(
            prompt=full_prompt, 
            output_path=img_path
        )
        
        if success:
            b64_uri = image_to_base64(img_path)
            replacements.append((match.span(), f"![{desc}]({b64_uri})"))
            logger.info(f"图片已转换为 base64: {desc[:30]}...")
        else:
            logger.warning(f"图片生成跳过: {desc}")
            replacements.append((match.span(), f"![{desc}](https://placehold.co/800x400/FFF9E6/FF9E66.png?text={desc})"))

    new_content = list(content) 
    for (start, end), replacement in reversed(replacements):
        new_content[start:end] = list(replacement)
    
    return "".join(new_content)


def embed_local_images(content: str, base_dir: Path) -> str:
    """
    扫描 Markdown 中已有的本地图片路径 `![alt](path/to/image.png)`
    将其转换为 base64 内嵌格式
    """
    # 正则匹配: ![任意alt](本地路径) - 排除已经是 data: 或 http 的
    pattern = r'!\[([^\]]*)\]\((?!data:|https?://)([^)]+)\)'
    
    matches = list(re.finditer(pattern, content))
    
    if not matches:
        return content
    
    replacements = []
    
    for match in matches:
        alt_text = match.group(1)
        img_path_str = match.group(2)
        
        # 解析图片路径（相对于 Markdown 文件所在目录）
        img_path = base_dir / img_path_str
        
        if img_path.exists():
            logger.info(f"内嵌本地图片: {img_path}")
            b64_uri = image_to_base64(img_path)
            replacements.append((match.span(), f"![{alt_text}]({b64_uri})"))
        else:
            logger.warning(f"图片文件不存在，跳过: {img_path}")
    
    # 倒序替换
    new_content = list(content)
    for (start, end), replacement in reversed(replacements):
        new_content[start:end] = list(replacement)
    
    return "".join(new_content)


# ============================================
# CSS Inlining Module (New)
# ============================================

def get_style_mapping() -> dict:
    """
    Define inline styles based on wechat_style.css
    Since simple parsing is error-prone without heavy deps, we hardcode key mappings here
    matching the known template.
    """
    return {
        "body": "font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif; line-height: 1.75; color: #333333; background: #FAF9F5; margin: 0; padding: 0;",
        "h1": "font-size: 1.6rem; font-weight: 700; color: #222; margin-bottom: 24px; line-height: 1.4;",
        "h2": "display: inline-block; background: #E9C4B1; color: #222; font-size: 1.15rem; padding: 4px 16px; border-radius: 20px; margin: 40px 0 20px; font-weight: 600; box-shadow: 2px 2px 0px rgba(0, 0, 0, 0.05);",
        "h3": "font-size: 1.05rem; font-weight: 600; color: #333333; margin: 28px 0 12px; border-left: 4px solid #FF9E66; padding-left: 10px; line-height: 1.2;",
        "p": "margin-bottom: 20px; text-align: justify; letter-spacing: 0.03em; font-size: 1rem;",
        "strong": "color: #D35400; background: linear-gradient(180deg, transparent 65%, rgba(255, 158, 102, 0.2) 65%); padding: 0 2px;",
        "blockquote": "background: #FFF9E6; border-left: 4px solid #FF9E66; border-radius: 12px; padding: 16px 20px; margin: 24px 0; color: #5F5F5F; font-size: 0.95rem;",
        "ul": "padding-left: 20px; margin-bottom: 24px; color: #5F5F5F;",
        "ol": "padding-left: 20px; margin-bottom: 24px; color: #5F5F5F;",
        "li": "margin-bottom: 8px;",
        "pre": "background: #282C34; border-radius: 12px; padding: 40px 20px 20px; position: relative; overflow-x: auto; margin: 24px 0; color: #ABB2BF; font-size: 0.85rem; line-height: 1.6;",
        "code": "font-family: 'Fira Code', Consolas, monospace;",
        "img": "display: block; max-width: 100%; border-radius: 12px; margin: 24px auto; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);",
        "hr": "border: 0; height: 1px; background: #E0E0E0; margin: 40px 60px;",
        "article_container": "max-width: 680px; margin: 0 auto; background: #FAF9F5; min-height: 100vh;",
        "article_content": "padding: 24px 20px 60px; background: #FAF9F5;"
    }

def apply_inline_styles(soup: BeautifulSoup) -> None:
    """Apply inline styles to elements based on the mapping"""
    styles = get_style_mapping()
    
    # 1. Apply tag-based styles
    for tag in styles:
        if tag in ["body", "article_container", "article_content"]: continue
        
        for element in soup.find_all(tag):
            # Prepend existing style if any, but usually we just append or merge
            # Simple merge: new style + old style
            current_style = element.get('style', '')
            new_style = styles[tag]
            # If element has style, we append the template style BEFORE it so element specific style overrides? 
            # Or usually template first.
            # Strategy: Set template style, then append what was there (if specifically manually set).
            # But wait, soup.find_all might return elements we already touched? No.
            
            # Special case: Inline code vs Block code
            if tag == "code":
                if element.parent.name == "pre": continue # Handled by pre stlying mostly
                # Inline code styling
                inline_code_style = "background: #F0EEE6; color: #C04848; padding: 2px 6px; border-radius: 4px; font-size: 0.9em;"
                element['style'] = inline_code_style + current_style
                continue

            element['style'] = new_style + " " + current_style

    # 2. Special Classes (First P)
    # .article-content > p:first-of-type
    # This is hard to select exactly with simple loops, lets look for the first p in article content
    # Assuming article content wrapper is not yet there in 'soup' passed here? 
    # Usually we process the BODY HTML fragment.
    
    first_p = soup.find("p")
    if first_p:
        first_p_style = "background: #FFF; border: 1px solid #EAEAEA; padding: 24px; border-radius: 12px; font-size: 1.05rem; color: #444; box-shadow: 0 8px 16px rgba(0, 0, 0, 0.04); position: relative; overflow: hidden;"
        # Pseudo-elements like ::before cannot be inlined directly into style="" attribute.
        # We simulate the top bar with a real div if we want, or just accept basic styling.
        # Let's verify if we want to inject a div for the top bar.
        # For simplicity, we skip the pseudo-element 'top bar' in inline logic or add a border-top.
        # Let's add border-top as approximation
        first_p_style += " border-top: 4px solid #FF9E66;" 
        
        current_style = first_p.get('style', '')
        first_p['style'] = first_p_style + " " + current_style


# ============================================
# CSS & HTML Module
# ============================================

def load_css() -> str:
    """加载 CSS"""
    css_path = Path(__file__).parent.parent / "templates" / "wechat_style.css"
    if css_path.exists():
        return css_path.read_text(encoding="utf-8")
    return "" 


def markdown_to_html(content: str) -> str:
    """Markdown 转 Body HTML"""
    extensions = [
        "markdown.extensions.extra",
        "markdown.extensions.codehilite",
        "markdown.extensions.toc",
        "markdown.extensions.tables",
    ]
    return markdown.markdown(content, extensions=extensions)


def build_full_html(body: str, title: str) -> str:
    css = load_css()
    
    # 一键复制按钮样式
    copy_btn_css = """
/* 一键复制按钮样式 */
.copy-btn {
  position: fixed;
  top: 20px;
  right: 20px;
  padding: 12px 24px;
  background: linear-gradient(135deg, #FF9E66, #E9C4B1);
  color: #fff;
  border: none;
  border-radius: 25px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 4px 15px rgba(255, 158, 102, 0.4);
  transition: all 0.3s ease;
  z-index: 9999;
  display: flex;
  align-items: center;
  gap: 8px;
}

.copy-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(255, 158, 102, 0.5);
}

.copy-btn:active {
  transform: translateY(0);
}

.copy-btn.success {
  background: linear-gradient(135deg, #27C93F, #52D668);
}

.copy-btn svg {
  width: 18px;
  height: 18px;
  fill: currentColor;
}

.copy-toast {
  position: fixed;
  top: 80px;
  right: 20px;
  padding: 12px 20px;
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  border-radius: 8px;
  font-size: 14px;
  opacity: 0;
  transform: translateY(-10px);
  transition: all 0.3s ease;
  z-index: 9999;
}

.copy-toast.show {
  opacity: 1;
  transform: translateY(0);
}

@media print {
  .copy-btn, .copy-toast { display: none !important; }
}
"""
    
    # 一键复制 JavaScript
    copy_script = """
<script>
function copyArticleContent() {
  // Select the container so that we capture the inner div with its background style
  const articleContent = document.querySelector('.article-container');
  const btn = document.querySelector('.copy-btn');
  const toast = document.getElementById('copyToast');

  const range = document.createRange();
  range.selectNodeContents(articleContent);

  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);

  try {
    const success = document.execCommand('copy');
    if (success) {
      btn.classList.add('success');
      btn.querySelector('span').textContent = '复制成功！';
      toast.classList.add('show');

      setTimeout(() => {
        btn.classList.remove('success');
        btn.querySelector('span').textContent = '一键复制';
        toast.classList.remove('show');
      }, 2000);
    } else {
      throw new Error('复制失败');
    }
  } catch (err) {
    toast.textContent = '复制失败，请手动选择复制';
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
      toast.textContent = '复制成功！可直接粘贴到微信公众号';
    }, 2000);
  }

  selection.removeAllRanges();
}
</script>
"""
    
    # 复制按钮 HTML
    copy_btn_html = """
<!-- 一键复制按钮 -->
<button class="copy-btn" onclick="copyArticleContent()">
  <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
  </svg>
  <span>一键复制</span>
</button>
<div class="copy-toast" id="copyToast">复制成功！可直接粘贴到微信公众号</div>
"""
    
    template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="generator" content="WeChat Article Gen (TechFastFood)">
    <title>{title}</title>
    <style>
{css}
{copy_btn_css}
    </style>
</head>
<body>
{copy_btn_html}
{copy_script}
    <!-- WeChat Outer Wrapper to Enforce Background -->
    <section id="wechat-wrapper" style="background-color: #FAF9F5; min-height: 100vh; font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif; color: #333333; line-height: 1.75;">
        <div class="article-container" style="max-width: 680px; margin: 0 auto; background: #FAF9F5;">
            <div class="article-content" style="padding: 24px 20px 60px; background: #FAF9F5;">
{body}
            </div>
        </div>
    </section>
</body>
</html>"""
    return template


# ============================================
# Calibration Module
# ============================================

def calibrate_code(html_content: str) -> str:
    """
    代码校准功能
    1. 清理空标签
    2. 修复可能的未闭合标签 (通过 soup)
    3. 移除冗余换行
    """
    logger.info("执行代码校准与样式内联...")
    
    soup = BeautifulSoup(html_content, "html.parser")
    
    # NEW: Phase 4.1 Apply Inline Styles
    apply_inline_styles(soup)
    
    # 移除空的 p 标签
    for p in soup.find_all("p"):
        if not p.get_text(strip=True) and not p.find("img"):
            p.decompose()
            
    return str(soup)


# ============================================
# Main Pipeline
# ============================================

def main():
    parser = argparse.ArgumentParser(description="公众号文章生成器 V2 (Gemini 3 Pro)")
    parser.add_argument("input", type=Path, help="Input Markdown file")
    parser.add_argument("-o", "--output", type=Path, help="Output HTML file")
    parser.add_argument("--preview", action="store_true", help="Browser preview")
    args = parser.parse_args()

    if not args.input.exists():
        logger.error("输入文件不存在")
        return

    # 1. 读取内容
    content = args.input.read_text(encoding="utf-8")
    # 简单的标题提取逻辑
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title_match.group(1) if title_match else "科技速食科普"
    
    # 2. 处理图片 (Phase 1.5) - 配置从 .env 读取
    logger.info(f"图片生成配置: Resolution={IMAGE_RESOLUTION}, Search={ENABLE_SEARCH}")
    assets_dir = args.input.parent / "assets"
    assets_dir.mkdir(exist_ok=True)
    
    content_with_images = process_images(content, assets_dir)
    
    # 2.5 内嵌本地图片为 base64
    content_with_embedded = embed_local_images(content_with_images, args.input.parent)
    
    # 3. 转换为 HTML (Phase 2)
    body_html = markdown_to_html(content_with_embedded)
    full_html = build_full_html(body_html, title)
    
    # 4. 代码校准 (Final Polish)
    final_html = calibrate_code(full_html)
    
    # 5. 保存
    output_path = args.output or args.input.with_suffix(".html")
    output_path.write_text(final_html, encoding="utf-8")
    
    logger.info(f"HTML 已生成: {output_path}")
    
    if args.preview:
        import webbrowser
        webbrowser.open(output_path.resolve().as_uri())

if __name__ == "__main__":
    main()
