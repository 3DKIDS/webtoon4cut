import streamlit as st
import openai
import requests
import os
import json
import base64
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import time

from openai import OpenAI

# OpenAI 클라이언트 초기화 (초기에는 None)
client = None

# 앱 타이틀 및 설정
st.set_page_config(
    page_title="내 사진 기반 웹툰 생성기",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 필요한 디렉토리 생성
if not os.path.exists("images"):
    os.makedirs("images")

if not os.path.exists("fonts"):
    os.makedirs("fonts")

# 폰트 다운로드 함수 (한글 폰트가 없을 경우)
def download_nanum_font():
    font_path = "fonts/NanumGothic.ttf"
    if not os.path.exists(font_path):
        try:
            font_url = "https://github.com/googlefonts/nanum-gothic/raw/main/fonts/NanumGothic-Regular.ttf"
            response = requests.get(font_url)
            with open(font_path, "wb") as f:
                f.write(response.content)
            return font_path
        except Exception as e:
            st.warning(f"폰트 다운로드 실패: {e}. 시스템 폰트를 사용합니다.")
            return None
    return font_path

# 폰트 가져오기 (먼저, 시스템 폰트 경로에서 확인)
def get_font(size=30):
    common_font_paths = [
        "C:/Windows/Fonts/malgun.ttf",  # Windows
        "C:/Windows/Fonts/NotoSansKR-Regular.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",  # Linux
        "/System/Library/Fonts/AppleGothic.ttf",  # macOS
    ]
    for path in common_font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    downloaded_font = download_nanum_font()
    if downloaded_font and os.path.exists(downloaded_font):
        return ImageFont.truetype(downloaded_font, size)
    return ImageFont.load_default()

# 에러 핸들링 함수
def handle_openai_error(e):
    error_message = str(e)
    if "400" in error_message:
        return "API 요청이 올바르지 않습니다. 이미지 프롬프트가 OpenAI 정책을 위반했거나, API 키가 유효하지 않을 수 있습니다."
    elif "401" in error_message:
        return "API 키가 유효하지 않거나 만료되었습니다."
    elif "429" in error_message:
        return "API 요청 횟수 제한을 초과했습니다. 잠시 후 다시 시도해주세요."
    elif "500" in error_message:
        return "OpenAI 서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
    else:
        return f"오류가 발생했습니다: {error_message}"

# 사이드바 설정
st.sidebar.title("⚙️ 설정")
api_key = st.sidebar.text_input("OpenAI API 키", type="password", value="")
if api_key:
    os.environ["OPENAI_API_KEY"] = api_key
    openai.api_key = api_key
    client = openai.OpenAI(api_key=api_key)  # ★ 여기서만 인스턴스 생성 ★

# 프레임 이미지 생성 함수
def create_frame_images():
    # ... (생략: A~D 프레임 생성, 기존 동일)
    a_frame = Image.new('RGB', (512, 512), color='white')
    draw = ImageDraw.Draw(a_frame)
    draw.rectangle([(0, 0), (255, 255)], outline='black', width=2)
    draw.rectangle([(256, 0), (511, 255)], outline='black', width=2)
    draw.rectangle([(0, 256), (255, 511)], outline='black', width=2)
    draw.rectangle([(256, 256), (511, 511)], outline='black', width=2)
    a_frame.save("images/A_Frame.png")
    # B, C, D 동일하게 프레임 생성 및 저장...

for frame_type in ["A", "B", "C", "D"]:
    if not os.path.exists(f"images/{frame_type}_Frame.png"):
        create_frame_images()
        break

def get_frame_image_path(frame_type):
    return f"images/{frame_type}_Frame.png"

# 앱 타이틀
st.title("🎨 내 사진 기반 4컷 웹툰 생성기")
st.markdown("당신의 사진과 스토리를 입력하면 DALL-E 3로 당신을 주인공으로 한 웹툰을 생성해주는 서비스입니다.")
st.markdown("원하는 프레임 레이아웃(A, B, C, D)을 선택하고 이미지를 생성하세요!")

# 이미지 인코딩
def encode_image(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')

# 사진 분석
def analyze_photo(photo_base64):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 사진을 분석하는 전문가입니다. 사람의 사진을 분석하여 외모적 특징을 자세히 설명해주세요. 나이, 성별, 머리 스타일, 얼굴 특징, 표정, 옷차림 등을 포함하세요. 웹툰 캐릭터를 만들기 위한 설명이어야 합니다."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "이 사진의 인물을 분석해서 웹툰 캐릭터로 만들기 위한 상세한 설명을 제공해주세요."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{photo_base64}"}}
                    ]
                }
            ],
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(handle_openai_error(e))
        return None

# 함수: OpenAI GPT를 사용하여 스토리 분석 및 패널 설명 생성
def analyze_story(story_text, character_description, num_panels, frame_layout):
    system_prompt = f"""당신은 웹툰 작가입니다. 사용자의 스토리를 {num_panels}컷으로 나누어 각 컷마다 어떤 장면이 그려져야 할지 상세히 설명해주세요.
    사용자가 업로드한 사진을 기반으로 한 캐릭터를 주인공으로 설정하고, 제공된 캐릭터 설명을 활용하세요.
    
    선택된 프레임 레이아웃은 '{frame_layout}' 입니다. 각 패널의 크기와 배치에 맞게 장면을 구성해주세요.
    
    반드시 각 패널에 한국어 대화 내용을 포함해야 합니다. 한국어로 자연스러운 대화를 생성해주세요.
    
    JSON 형식으로 다음과 같이 반환해주세요:
    {{
        "panels": [
            {{
                "description": "1번 패널 상세 설명 (캐릭터의 특징을 잘 반영)",
                "dialogue": "한국어 대사(필수)"
            }},
            ...
            {{
                "description": "{num_panels}번 패널 상세 설명 (캐릭터의 특징을 잘 반영)",
                "dialogue": "한국어 대사(필수)"
            }}
        ]
    }}
    
    대화는 반드시 한국어로 작성하고, 각 패널마다 포함해주세요. 대사는 간결하게 작성하되, 스토리를 잘 전달할 수 있어야 합니다.
    """
    
    user_prompt = f"""다음 스토리를 {num_panels}컷 웹툰으로 만들고 싶습니다. 각 컷마다 어떤 장면이 그려져야 할지 자세히 설명해주세요.

스토리: {story_text}

주인공 캐릭터 설명 (업로드된 사진 기반): 
{character_description}

선택된 레이아웃: {frame_layout}

이 캐릭터를 주인공으로 한 웹툰을 생성해주세요. 캐릭터의 외모적 특징을 각 패널 설명에 잘 반영해주세요.
각 패널에 한국어 대사나 나레이션을 반드시 추가해주세요. 간결하고 자연스러운 한국어 대화를 포함해주세요."""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        st.error(handle_openai_error(e))
        return None

# 함수: DALL-E 3 프롬프트 생성 (말풍선 없이 장면만 생성)
def create_prompts(panel_descriptions, style, character_description, num_panels, layout):
    system_prompt = f"""당신은 DALL-E 3 프롬프트 전문가입니다. 웹툰 장면 설명을 DALL-E 3가 잘 이해할 수 있는 상세한 프롬프트로 변환해주세요.
    사용자가 업로드한 사진을 기반으로 한 캐릭터를 정확하게 묘사하세요.
    
    사용자가 선택한 웹툰 레이아웃은 '{layout}'입니다. 이것은 {num_panels}컷 웹툰입니다.
    
    중요: 말풍선이나 텍스트는 포함하지 마세요. 나중에 별도로 추가할 것입니다.
    
    JSON 형식으로 다음과 같이 반환해주세요:
    {{
        "prompts": [
            "1번 패널을 위한 DALL-E 프롬프트 (말풍선 없음)",
            ...
            "{num_panels}번 패널을 위한 DALL-E 프롬프트 (말풍선 없음)"
        ]
    }}
    
    각 프롬프트에는 반드시 다음 요소를 강조해주세요:
    1. 웹툰 스타일과 선명한 이미지 품질
    2. 캐릭터의 특징과 표현
    3. 장면 설명 (대화 상황에 맞는 표정과 제스처)
    4. 단일 웹툰 패널임을 명시 (4컷 웹툰의 한 장면임을 명시)
    
    말풍선이나 텍스트는 절대 포함하지 마세요. 말풍선과 대화는 이미지 생성 후 별도로 추가할 것입니다.
    """
    
    user_prompt = f"""다음 웹툰 장면 설명을 DALL-E 3를 위한 상세한 프롬프트로 변환해주세요.
    
    웹툰 스타일: {style}
    웹툰 레이아웃: {layout}
    컷 수: {num_panels}컷 웹툰
    
    주인공 캐릭터 설명 (업로드된 사진 기반): 
    {character_description}
    
    장면 설명: {json.dumps(panel_descriptions, ensure_ascii=False)}
    
    각 프롬프트에는 다음 필수 요소를 포함해주세요:
    1. "단일 웹툰 패널, {style}, 선명한 이미지, 한국식 웹툰 스타일"
    2. 캐릭터의 특징과 표현을 정확히 묘사
    3. 대화 내용에 맞는 표정과 제스처 묘사
    
    중요: 말풍선이나 텍스트는 포함하지 마세요. 말풍선과 대화는 나중에 별도로 추가할 것입니다.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        st.error(handle_openai_error(e))
        return None

# 함수: DALL-E 3로 이미지 생성 (말풍선 없는 장면만)
def generate_image(prompt, style, user_photo_description):
    # 프롬프트에 사용자 특징 강조 추가
    if len(user_photo_description) > 150:
        user_photo_description = user_photo_description[:150] + "..."
    
    # 프롬프트 길이 제한 (DALL-E 3 제한: 약 4000자)
    max_prompt_length = 3800
    
    # 말풍선 없는 이미지 요청
    enhanced_prompt = f"{prompt}, 캐릭터 특징: {user_photo_description}, 스타일: {style}, 단일 웹툰 패널, 말풍선이나 텍스트 없음"
    
    if len(enhanced_prompt) > max_prompt_length:
        # 길이가 초과하면 중요하지 않은 부분 줄이기
        excess = len(enhanced_prompt) - max_prompt_length
        user_photo_description = user_photo_description[:max(50, len(user_photo_description)-excess-100)] + "..."
        enhanced_prompt = f"{prompt}, 캐릭터 특징: {user_photo_description}, 스타일: {style}, 단일 웹툰 패널, 말풍선이나 텍스트 없음"
    
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=enhanced_prompt,
            n=1,
            size="1024x1024",
            quality="standard",
            style="vivid"
        )
        
        image_url = response.data[0].url
        return image_url
    except Exception as e:
        error_msg = handle_openai_error(e)
        st.error(f"이미지 생성 중 오류가 발생했습니다: {error_msg}")
        
        # 오류 발생 시 간단한 프롬프트로 재시도
        try:
            simplified_prompt = f"웹툰 한 장면, {style} 스타일, 말풍선이나 텍스트 없음"
            response = client.images.generate(
                model="dall-e-3",
                prompt=simplified_prompt,
                n=1,
                size="1024x1024",
                quality="standard",
                style="vivid"
            )
            
            image_url = response.data[0].url
            st.success("단순화된 프롬프트로 이미지 생성에 성공했습니다.")
            return image_url
        except:
            return None

# 함수: 이미지 URL에서 이미지 다운로드
def get_image_from_url(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # 오류 검사
        return Image.open(BytesIO(response.content))
    except Exception as e:
        st.error(f"이미지 다운로드 오류: {str(e)}")
        return None

# 이미지에 말풍선과 텍스트 추가
def add_speech_bubble(image, text, bubble_type="기본 방울형"):
    img = image.copy()
    width, height = img.size
    draw = ImageDraw.Draw(img)
    
    # 한글 폰트 로드
    try:
        font = get_font(size=30)
    except Exception as e:
        st.warning(f"폰트 로드 실패: {e}. 기본 폰트를 사용합니다.")
        font = ImageFont.load_default()
    
    # 텍스트 줄바꿈 처리
    def wrap_text(text, width_chars=15):
        words = text.split(' ')
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            if current_length + len(word) + 1 <= width_chars:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
        
        if current_line:
            lines.append(' '.join(current_line))
            
        # 한글 텍스트의 경우 특별 처리 (공백이 적을 수 있음)
        if len(lines) == 1 and len(text) > width_chars:
            lines = []
            for i in range(0, len(text), width_chars):
                lines.append(text[i:i+width_chars])
                
        return lines
    
    wrapped_text = wrap_text(text)
    textwidth, textheight = max([draw.textlength(line, font=font) for line in wrapped_text]), len(wrapped_text) * font.size + 10
    
    # 말풍선 위치 결정 (이미지 상단에 배치)
    margin = 20
    bubble_x = (width - textwidth) // 2 - margin
    bubble_y = margin
    bubble_width = textwidth + margin * 2
    bubble_height = textheight + margin * 2
    
    # 말풍선 그리기
    if bubble_type == "구름형":
        # 구름형 말풍선 (사고/생각)
        cloud_radius = 15
        # 큰 원 그리기
        for i in range(0, 360, 30):
            x = bubble_x + bubble_width//2 + int(cloud_radius * 1.5 * abs(i % 90 - 45) / 45) * (1 if i < 180 else -1)
            y = bubble_y + bubble_height//2 + int(cloud_radius * 1.5 * abs((i+90) % 90 - 45) / 45) * (1 if i < 270 and i > 90 else -1)
            r = cloud_radius + int(cloud_radius * 0.5 * (i % 60) / 60)
            draw.ellipse((x-r, y-r, x+r, y+r), fill='white', outline='black', width=2)
    elif bubble_type == "직사각형":
        # 직사각형 말풍선
        draw.rectangle([bubble_x, bubble_y, bubble_x + bubble_width, bubble_y + bubble_height], 
                      fill='white', outline='black', width=2)
    elif bubble_type == "타원형":
        # 타원형 말풍선
        draw.ellipse([bubble_x, bubble_y, bubble_x + bubble_width, bubble_y + bubble_height], 
                    fill='white', outline='black', width=2)
    else:  # 기본 방울형
        # 기본 말풍선 (대화)
        draw.ellipse([bubble_x, bubble_y, bubble_x + bubble_width, bubble_y + bubble_height], 
                    fill='white', outline='black', width=2)
        # 꼬리 추가
        tip_points = [
            (bubble_x + bubble_width//2 - 15, bubble_y + bubble_height),
            (bubble_x + bubble_width//2, bubble_y + bubble_height + 15),
            (bubble_x + bubble_width//2 + 15, bubble_y + bubble_height)
        ]
        draw.polygon(tip_points, fill='white', outline='black', width=2)
    
    # 텍스트 그리기
    text_x = bubble_x + margin
    text_y = bubble_y + margin
    
    for line in wrapped_text:
        draw.text((text_x, text_y), line, font=font, fill='black')
        text_y += font.size + 5  # 줄 간격
    
    return img

# 프레임 레이아웃에 따른 이미지 합성 함수
def create_layout_image(images, layout_type):
    """선택된 레이아웃에 따라 이미지를 합성합니다."""
    
    # 이미지가 충분하지 않으면 빈 이미지로 채우기
    while len(images) < 4:
        blank = Image.new('RGB', (1024, 1024), color='white')
        images.append(blank)
    
    # 레이아웃별 이미지 합성 처리
    if layout_type == "A":  # 2x2 그리드 레이아웃
        width = 2048
        height = 2048
        combined = Image.new('RGB', (width, height), color='white')
        
        # 패널 배치 (2x2 그리드)
        positions = [(0, 0), (1024, 0), (0, 1024), (1024, 1024)]
        for i, img in enumerate(images[:4]):
            img_resized = img.resize((1024, 1024))
            combined.paste(img_resized, positions[i])
    
    elif layout_type == "B":  # 세로 레이아웃
        panel_height = 768  # 각 패널 높이
        width = 1024
        
        # 각 패널 크기 조정
        resized_images = []
        for img in images[:4]:
            resized = img.resize((width, panel_height))
            resized_images.append(resized)
        
        # 4컷 세로형 웹툰 레이아웃 생성
        total_height = panel_height * 4 + 60  # 패널 사이 여백 추가
        combined = Image.new('RGB', (width, total_height), color='white')
        
        # 패널 배치
        for i, img in enumerate(resized_images):
            y_offset = i * (panel_height + 20)  # 20픽셀 여백
            combined.paste(img, (0, y_offset))
    
    elif layout_type == "C":  # 위 1컷 + 아래 2컷 레이아웃
        width = 2048
        height = 2048
        combined = Image.new('RGB', (width, height), color='white')
        
        # 이미지 크기 조정
        top_image = images[0].resize((width, 1024))
        bottom_left = images[1].resize((1024, 1024))
        bottom_right = images[2].resize((1024, 1024))
        
        # 이미지 배치
        combined.paste(top_image, (0, 0))
        combined.paste(bottom_left, (0, 1024))
        combined.paste(bottom_right, (1024, 1024))
        
    elif layout_type == "D":  # 세로 긴 2컷 + 옆 1컷 레이아웃
        width = 2048
        height = 2048
        combined = Image.new('RGB', (width, height), color='white')
        
        # 이미지 크기 조정
        left_image = images[0].resize((1024, 2048))
        right_top = images[1].resize((1024, 1024))
        right_bottom = images[2].resize((1024, 1024))
        
        # 이미지 배치
        combined.paste(left_image, (0, 0))
        combined.paste(right_top, (1024, 0))
        combined.paste(right_bottom, (1024, 1024))
    
    else:  # 기본 2x2 그리드
        width = 2048
        height = 2048
        combined = Image.new('RGB', (width, height), color='white')
        
        # 패널 배치 (2x2 그리드)
        positions = [(0, 0), (1024, 0), (0, 1024), (1024, 1024)]
        for i, img in enumerate(images[:4]):
            img_resized = img.resize((1024, 1024))
            combined.paste(img_resized, positions[i])
    
    return combined

# 탭 설정: 웹툰 생성 / 설정
tab1, tab2 = st.tabs(["웹툰 생성", "스타일 가이드"])

with tab1:
    # 중요: 스타일 선택 부분을 폼 바깥으로 이동하여 즉시 반응하도록 함
    st.subheader("웹툰 스타일 선택")
    style_col1, style_col2 = st.columns(2)
    
    with style_col1:
        style_category = st.selectbox("스타일 카테고리", [
            "애니메이션/만화 스타일", 
            "예술 스타일", 
            "게임/디지털 스타일",
            "기타 스타일"
        ])
    
    with style_col2:
        # 카테고리별 세부 스타일 옵션
        if style_category == "애니메이션/만화 스타일":
            style_options = [
                "지브리 스튜디오 - 하울의 움직이는 성 스타일",
                "지브리 스튜디오 - 센과 치히로의 행방불명 스타일",
                "지브리 스튜디오 - 토토로 스타일",
                "지브리 스튜디오 - 모노노케 히메 스타일",
                "디즈니 클래식 애니메이션 스타일",
                "디즈니 3D 애니메이션 스타일",
                "픽사 3D 애니메이션 스타일",
                "한국식 웹툰 스타일 (LINE 웹툰)",
                "일본 망가 - 소년 만화 스타일",
                "일본 망가 - 소녀 만화 스타일",
                "미국 마블 코믹스 스타일",
                "미국 DC 코믹스 스타일",
                "심슨 가족 스타일",
                "파워퍼프걸 스타일",
                "어드벤처 타임 스타일",
                "아바타: 마지막 에어벤더 스타일"
            ]
        elif style_category == "예술 스타일":
            style_options = [
                "수채화 스타일",
                "유화 스타일",
                "인상주의 스타일",
                "팝아트 스타일",
                "미니멀리즘 스타일",
                "초현실주의 스타일",
                "아르누보 스타일",
                "수묵화 스타일",
                "고흐 스타일",
                "피카소 스타일",
                "모네 스타일",
                "앤디 워홀 스타일"
            ]
        elif style_category == "게임/디지털 스타일":
            style_options = [
                "픽셀 아트 스타일",
                "로블록스 스타일",
                "마인크래프트 스타일",
                "포트나이트 스타일",
                "사이버펑크 스타일",
                "베이퍼웨이브 스타일",
                "로우 폴리 3D 스타일",
                "레트로 게임 스타일",
                "젤다의 전설: 눈물의 왕국 스타일"
            ]
        else:  # 기타 스타일
            style_options = [
                "클레이 애니메이션 스타일",
                "스톱모션 스타일",
                "빈티지 포스터 스타일",
                "네온 사인 스타일",
                "스케치북 스타일",
                "스티커 아트 스타일",
                "콜라주 스타일",
                "신문 만화 스타일",
                "실루엣 스타일",
                "파스텔 색상 스타일"
            ]
        
        selected_style = st.selectbox("세부 스타일", style_options)
        
    # 사용자 정의 스타일 입력    
    custom_style = st.text_input("직접 스타일 입력 (선택사항)", 
                                placeholder="원하는 스타일이 위 목록에 없다면 직접 입력하세요")
        
    # 최종 스타일 표시
    final_style = custom_style if custom_style else selected_style
    st.info(f"선택된 스타일: {final_style}")
    
    # 레이아웃 선택 UI (이미지 버튼)
    st.subheader("웹툰 레이아웃 선택")
    st.markdown("원하는 4컷 레이아웃을 선택하세요.")
    
    # 레이아웃 이미지 옵션 표시
    col1, col2, col3, col4 = st.columns(4)
    
    # 각 레이아웃 이미지 표시 및 선택 버튼
    layouts = {
        "A": "2x2 그리드 (기본)",
        "B": "세로형",
        "C": "상단 1컷 + 하단 2컷",
        "D": "좌측 세로 + 우측 2컷"
    }
    
    # 세션 상태 초기화
    if 'selected_layout' not in st.session_state:
        st.session_state.selected_layout = "A"
    
    with col1:
        st.image("images/A_Frame.png", caption=layouts["A"], width=150)
        if st.button("A 레이아웃"):
            st.session_state.selected_layout = "A"
    
    with col2:
        st.image("images/B_Frame.png", caption=layouts["B"], width=150)
        if st.button("B 레이아웃"):
            st.session_state.selected_layout = "B"
    
    with col3:
        st.image("images/C_Frame.png", caption=layouts["C"], width=150)
        if st.button("C 레이아웃"):
            st.session_state.selected_layout = "C"
    
    with col4:
        st.image("images/D_Frame.png", caption=layouts["D"], width=150)
        if st.button("D 레이아웃"):
            st.session_state.selected_layout = "D"
    
    # 선택된 레이아웃 표시
    st.success(f"선택된 레이아웃: {layouts[st.session_state.selected_layout]}")
    
    # 레이아웃 설명 표시
    layout_descriptions = {
        "A": "2x2 그리드 레이아웃: 4개의 패널이 정사각형으로 배치됩니다.",
        "B": "세로형 레이아웃: 4개의 패널이 세로로 길게 배치됩니다.",
        "C": "상단 1컷 + 하단 2컷 레이아웃: 상단에 큰 패널 1개, 하단에 작은 패널 2개가 배치됩니다.",
        "D": "좌측 세로 + 우측 2컷 레이아웃: 좌측에 세로로 긴 패널 1개, 우측에 작은 패널 2개가 배치됩니다."
    }
    
    st.info(layout_descriptions[st.session_state.selected_layout])
    
    # 입력 폼 구성
    with st.form("webtoon_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            story_text = st.text_area("웹툰 스토리", 
                                    placeholder="웹툰으로 만들고 싶은 스토리를 입력하세요...",
                                    height=150)
            
            user_photo = st.file_uploader("내 사진 업로드 (필수)", type=["png", "jpg", "jpeg"])
            
            if user_photo:
                st.image(user_photo, caption="업로드된 사진", width=200)
                
            # 패널 수 고정 (4컷)
            st.write("**패널 수: 4컷**")
            num_panels = 4
            
            # 대화 포함 여부 (항상 포함)
            st.write("**대화(말풍선) 포함: 네**")
            include_dialogue = True
        
        with col2:
            # 추가 설정
            st.subheader("추가 설정")
            advanced_options = st.expander("고급 설정")
            with advanced_options:
                character_importance = st.slider("캐릭터 중요도", min_value=1, max_value=10, value=8, 
                                                help="높을수록 캐릭터의 외모 특징을 더 강조합니다")
                image_quality = st.select_slider("이미지 품질", options=["standard", "hd"], value="standard")
                image_style = st.select_slider("이미지 스타일", options=["natural", "vivid"], value="vivid")
                
                # 말풍선 스타일 선택 추가
                st.markdown("**말풍선 스타일**")
                bubble_style = st.select_slider("말풍선 스타일", 
                                               options=["기본 방울형", "구름형", "직사각형", "타원형"], 
                                               value="기본 방울형",
                                               help="생성되는 웹툰의 말풍선 스타일을 선택합니다")
                
                # 말풍선 텍스트 크기
                st.markdown("**말풍선 텍스트 크기**")
                text_size = st.slider("텍스트 크기", min_value=20, max_value=50, value=30,
                                    help="말풍선 안의 텍스트 크기를 조절합니다")
                
                # 스타일 참조 이미지 사용 옵션
                st.markdown("**스타일 가이드**")
                style_guide = st.selectbox("스타일 참조 가이드 포함", 
                                        ["없음", "약간 포함", "중간 정도 포함", "많이 포함"], 
                                        index=1,
                                        help="DALL-E에게 선택한 스타일의 특징을 얼마나 강조할지 선택합니다")
        
        # 폼 제출 버튼
        submit_button = st.form_submit_button("웹툰 생성하기")

    # 웹툰 생성 처리
    if submit_button:
        if not api_key:
            st.error("OpenAI API 키를 입력해주세요!")
        elif not story_text:
            st.error("웹툰 스토리를 입력해주세요!")
        elif not user_photo:
            st.error("내 사진을 업로드해주세요!")
        else:
            try:
                # 스타일 가이드에 따른 스타일 설명 추가
                style_guides = {
                    "지브리 스튜디오 - 하울의 움직이는 성 스타일": "파스텔 색조, 섬세한 배경 디테일, 부드러운 선, 자연과 마법이 어우러진 세계",
                    "지브리 스튜디오 - 센과 치히로의 행방불명 스타일": "환상적인 요소들, 풍부한 색상 팔레트, 동양적 미학, 복잡한 배경",
                    "지브리 스튜디오 - 토토로 스타일": "귀여운 캐릭터 디자인, 자연과 시골 풍경, 따뜻한 색감, 표현력 있는 캐릭터",
                    "지브리 스튜디오 - 모노노케 히메 스타일": "자연과 영적인 요소, 진한 색감, 다이내믹한 액션 장면, 복잡한 배경",
                    "디즈니 클래식 애니메이션 스타일": "부드러운 라인, 둥근 캐릭터 디자인, 풍부한 색상, 주인공에게 집중된 조명",
                    "디즈니 3D 애니메이션 스타일": "반짝이는 텍스처, 풍부한 색감, 영화적인 구도, 표현력 있는 캐릭터, 3D 렌더링",
                    "픽사 3D 애니메이션 스타일": "세밀한 텍스처, 정확한 라이팅, 감성적인 표현, 스타일화된 캐릭터",
                    "한국식 웹툰 스타일 (LINE 웹툰)": "깔끔한 선화, 플랫한 색상, 강한 윤곽선, 감정 표현을 위한 텍스트 효과, 세로 스크롤 포맷",
                    "일본 망가 - 소년 만화 스타일": "날카로운 선, 다이내믹한 액션 라인, 과장된 표정, 속도감 있는 효과선",
                    "일본 망가 - 소녀 만화 스타일": "섬세한 선, 반짝이는 눈, 꽃 패턴 배경, 감정 표현이 풍부한 얼굴",
                    "미국 마블 코믹스 스타일": "근육질의 캐릭터, 강한 윤곽선, 선명한 색상, 다이내믹한 포즈, 극적인 구도",
                    "미국 DC 코믹스 스타일": "어두운 톤, 강한 명암 대비, 도시 배경, 영웅적인 포즈, 사실적인 인체 비율"
                }
                
                # 선택된 스타일에 대한 추가 설명 가져오기
                style_description = ""
                if style_guide != "없음" and final_style in style_guides:
                    style_description = f", {style_guides[final_style]}"
                
                # 진행 상태 컨테이너
                status_container = st.empty()
                status_container.info("처리를 시작합니다...")
                
                # 선택된 레이아웃 가져오기
                layout_type = st.session_state.selected_layout
                
                with st.spinner("사진 분석 중..."):
                    # 사진 분석
                    status_container.info("업로드된 사진을 분석하는 중입니다...")
                    photo_base64 = encode_image(user_photo)
                    character_description = analyze_photo(photo_base64)
                    
                    if character_description:
                        st.success("사진 분석 완료!")
                        
                        # 사진 분석 결과 표시
                        with st.expander("사진 분석 결과"):
                            st.write(character_description)
                        
                        # 진행 상태 표시
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        status_text.text("스토리 분석 중...")
                        
                        # 스토리 분석
                        panel_descriptions = analyze_story(story_text, character_description, num_panels, layout_type)
                        progress_bar.progress(0.2)
                        
                        if panel_descriptions:
                            # 패널 설명과 대화 표시
                            with st.expander("자동 생성된 패널 설명 및 대화", expanded=True):
                                # 사용자 대화 입력 컨테이너
                                st.markdown("#### 패널별 설명 및 대화 수정")
                                st.markdown("필요한 경우 아래에서 대화를 수정할 수 있습니다.")
                                
                                # 각 패널의 대화 수정 입력 폼
                                panel_dialogues = {}
                                panel_descriptions_data = panel_descriptions["panels"]
                                
                                # 패널이 부족한 경우 더미 데이터 추가
                                while len(panel_descriptions_data) < num_panels:
                                    panel_descriptions_data.append({
                                        "description": f"패널 {len(panel_descriptions_data) + 1}",
                                        "dialogue": "안녕하세요!"  # 기본 한국어 대사 추가
                                    })
                                
                                # 패널 수에 맞게 조정
                                panel_descriptions_data = panel_descriptions_data[:num_panels]
                                
                                # 패널별 대화 수정 입력 받기
                                for i, panel in enumerate(panel_descriptions_data):
                                    st.markdown(f"**{i+1}번 패널**")
                                    st.markdown(f"**설명**: {panel['description']}")
                                    
                                    # 기존 대화 내용 표시
                                    default_dialogue = panel.get('dialogue', '')
                                    panel_dialogues[i] = st.text_area(
                                        f"대화/나레이션 #{i+1}", 
                                        value=default_dialogue,
                                        key=f"dialogue_{i}",
                                        help="말풍선에 들어갈 한국어 텍스트를 입력하세요."
                                    )
                                    st.divider()
                                
                                # 대화 수정 적용 버튼
                                update_dialogues = st.button("대화 수정 적용")
                                
                                if update_dialogues:
                                    # 수정된 대화 적용
                                    for i, panel in enumerate(panel_descriptions_data):
                                        if i in panel_dialogues:
                                            panel["dialogue"] = panel_dialogues[i]
                                
                                status_text.text("프롬프트 생성 중...")
                                
                                # 최종 스타일에 스타일 설명 추가
                                enhanced_style = final_style
                                if style_description:
                                    enhanced_style += style_description
                                
                                # DALL-E 프롬프트 생성 (말풍선 없이)
                                prompts = create_prompts(panel_descriptions_data, enhanced_style, character_description, num_panels, layout_type)
                                progress_bar.progress(0.4)
                                
                                if prompts:
                                    # 이미지 컨테이너 생성
                                    st.markdown("### 생성된 웹툰 패널")
                                    image_containers = []
                                    for i in range(num_panels):
                                        image_containers.append(st.empty())
                                    
                                    # 각 패널 이미지 생성
                                    panel_images = []
                                    panel_urls = []  # 이미지 URL 저장
                                    panel_errors = 0
                                    
                                    for i, prompt in enumerate(prompts["prompts"][:num_panels]):
                                        status_text.text(f"{i+1}번 패널 생성 중... ({i+1}/{num_panels})")
                                        
                                        # 이미지 생성 (캐릭터 특징 강조)
                                        simplified_description = " ".join(character_description.split(" ")[:20])  # 간략화
                                        
                                        # 스타일 설명 추가
                                        enhanced_prompt = prompt
                                        if style_description:
                                            enhanced_prompt += style_description
                                        
                                        # 대화 내용
                                        dialogue = panel_descriptions_data[i].get("dialogue", "")
                                        
                                        # 이미지 생성 시도 (최대 2회)
                                        for attempt in range(2):
                                            # 말풍선 없는 이미지 생성
                                            image_url = generate_image(enhanced_prompt, enhanced_style, simplified_description)
                                            
                                            if image_url:
                                                panel_urls.append(image_url)  # URL 저장
                                                
                                                img = get_image_from_url(image_url)
                                                if img:
                                                    # 이미지에 말풍선과 텍스트 추가
                                                    img_with_bubble = add_speech_bubble(img, dialogue, bubble_style)
                                                    panel_images.append(img_with_bubble)
                                                    image_containers[i].image(img_with_bubble, caption=f"{i+1}번 패널", use_container_width=True)
                                                break
                                            elif attempt < 1:
                                                # 첫 번째 시도 실패시 프롬프트 단순화하여 재시도
                                                st.warning(f"{i+1}번 패널 생성 중 오류 발생. 프롬프트를 단순화하여 다시 시도합니다...")
                                                simplified_prompt = f"단일 웹툰 패널, {final_style}, 말풍선이나 텍스트 없음"
                                                enhanced_prompt = simplified_prompt
                                            else:
                                                panel_errors += 1
                                                st.error(f"{i+1}번 패널 생성에 실패했습니다.")
                                        
                                        # 진행률 업데이트
                                        progress_bar.progress(0.4 + (i + 1) * (0.6 / num_panels))
                                    
                                    if len(panel_images) > 0:
                                        if len(panel_images) == num_panels:
                                            status_text.text("모든 패널 생성 완료!")
                                            progress_bar.progress(1.0)
                                            
                                            # 생성 완료 메시지
                                            st.success(f"당신을 주인공으로 한 {num_panels}컷 웹툰 생성이 완료되었습니다!")
                                        elif panel_errors > 0:
                                            st.warning(f"{panel_errors}개 패널 생성에 실패했습니다. 성공적으로 생성된 패널만 표시합니다.")
                                        
                                        # 이미지 다운로드 버튼
                                        st.markdown("### 개별 패널 다운로드")
                                        for i, img in enumerate(panel_images):
                                            col1, col2 = st.columns([3, 1])
                                            with col1:
                                                st.markdown(f"**{i+1}번 패널**")
                                                if i < len(panel_descriptions_data) and panel_descriptions_data[i].get("dialogue"):
                                                    st.markdown(f"**대사**: {panel_descriptions_data[i]['dialogue']}")
                                            with col2:
                                                buf = BytesIO()
                                                img.save(buf, format="PNG")
                                                buf.seek(0)
                                                st.download_button(
                                                    label=f"다운로드",
                                                    data=buf,
                                                    file_name=f"my_webtoon_panel_{i+1}.png",
                                                    mime="image/png"
                                                )
                                        
                                        # 선택된 레이아웃에 따라 이미지 합성
                                        try:
                                            st.markdown("### 레이아웃 웹툰 다운로드")
                                            
                                            # 선택된 레이아웃으로 이미지 합성
                                            layout_description = {
                                                "A": "2x2 그리드",
                                                "B": "세로형",
                                                "C": "상단 1컷 + 하단 2컷",
                                                "D": "좌측 세로 + 우측 2컷"
                                            }
                                            
                                            st.markdown(f"**선택된 레이아웃: {layout_description[layout_type]}**")
                                            
                                            # 이미지 합성
                                            combined_img = create_layout_image(panel_images, layout_type)
                                            
                                            # 합친 이미지 다운로드 버튼
                                            buf = BytesIO()
                                            combined_img.save(buf, format="PNG")
                                            buf.seek(0)
                                            
                                            st.download_button(
                                                label=f"{layout_description[layout_type]} 웹툰 다운로드",
                                                data=buf,
                                                file_name=f"my_webtoon_layout_{layout_type}.png",
                                                mime="image/png"
                                            )
                                            
                                            # 합친 이미지 표시
                                            st.image(combined_img, caption=f"{layout_description[layout_type]} 웹툰", use_container_width=True)
                                        
                                        except Exception as e:
                                            st.error(f"이미지 합치기 오류: {str(e)}")
                                            # 오류 발생 시 기본 세로 레이아웃으로 대체
                                            try:
                                                # 세로로 나열하는 기본 레이아웃
                                                width = panel_images[0].width
                                                total_height = sum(img.height for img in panel_images)
                                                combined_img = Image.new('RGB', (width, total_height), color='white')
                                                
                                                y_offset = 0
                                                for img in panel_images:
                                                    combined_img.paste(img, (0, y_offset))
                                                    y_offset += img.height
                                                
                                                # 합친 이미지 다운로드 버튼
                                                buf = BytesIO()
                                                combined_img.save(buf, format="PNG")
                                                buf.seek(0)
                                                
                                                st.download_button(
                                                    label="전체 웹툰 다운로드 (기본 레이아웃)",
                                                    data=buf,
                                                    file_name=f"my_complete_webtoon.png",
                                                    mime="image/png"
                                                )
                                                
                                                # 합친 이미지 표시
                                                st.image(combined_img, caption="전체 웹툰 (기본 레이아웃)", use_container_width=True)
                                            except Exception as e2:
                                                st.error(f"대체 레이아웃 생성 오류: {str(e2)}")
                                    else:
                                        st.error("모든 패널 생성에 실패했습니다.")
                                else:
                                    st.error("프롬프트 생성에 실패했습니다.")
                        else:
                            st.error("스토리 분석에 실패했습니다.")
                    else:
                        st.error("사진 분석에 실패했습니다.")
            
            except Exception as e:
                st.error(f"오류가 발생했습니다: {str(e)}")

with tab2:
    # 스타일 참조 이미지 및 설명
    st.header("다양한 이미지 스타일 가이드")
    st.markdown("""
    ### 애니메이션/만화 스타일
    
    #### 지브리 스튜디오 스타일
    - **지브리 스튜디오 - 하울의 움직이는 성 스타일**: 파스텔 색조, 섬세한 배경 디테일, 부드러운 선, 환상적인 건축물, 자연과 마법이 어우러진 세계
    - **지브리 스튜디오 - 센과 치히로의 행방불명 스타일**: 환상적인 요소들, 풍부한 색상 팔레트, 동양적 미학, 복잡한 배경, 독특한 캐릭터 디자인
    - **지브리 스튜디오 - 토토로 스타일**: 귀여운 캐릭터 디자인, 자연과 시골 풍경, 따뜻한 색감, 단순하면서도 표현력 있는 캐릭터
    - **지브리 스튜디오 - 모노노케 히메 스타일**: 자연과 영적인 요소, 진한 색감, 다이내믹한 액션 장면, 복잡한 배경 디테일
    
    #### 디즈니/픽사 스타일
    - **디즈니 클래식 애니메이션 스타일**: 부드러운 라인, 둥근 캐릭터 디자인, 풍부한 색상, 주인공에게 집중된 조명, 과장된 표정과 제스처
    - **디즈니 3D 애니메이션 스타일**: 반짝이는 텍스처, 풍부한 색감, 영화적인 구도, 표현력 있는 캐릭터, 현대적인 3D 렌더링
    - **픽사 3D 애니메이션 스타일**: 세밀한 텍스처, 물리적으로 정확한 라이팅, 감성적인 표현, 실사에 가까운 환경, 스타일화된 캐릭터
    
    #### 기타 만화 스타일
    - **한국식 웹툰 스타일**: 깔끔한 선화, 플랫한 색상, 강한 윤곽선, 감정 표현을 위한 텍스트 효과
    - **일본 망가 스타일**: 흑백 대비, 속도감 있는 효과선, 과장된 표정, 특징적인 눈 디자인
    - **미국 코믹스 스타일**: 근육질의 캐릭터, 강한 윤곽선, 선명한 색상, 다이내믹한 포즈
    
    ### 예술 스타일
    - **수채화 스타일**: 투명한 색상 레이어, 부드러운 경계, 자연스러운 색상 흐름, 미묘한 색조 변화
    - **유화 스타일**: 질감 있는 붓 터치, 풍부한 색감, 두꺼운 페인트 레이어, 명암 대비가 강한 표현
    - **팝아트 스타일**: 강렬한 색상, 단순화된 형태, 대중문화 요소, 반복 패턴, 두꺼운 윤곽선
    - **미니멀리즘 스타일**: 단순한 형태, 제한된 색상 팔레트, 여백의 활용, 불필요한 요소 제거
    
    ### 게임/디지털 스타일
    - **픽셀 아트 스타일**: 정사각형 픽셀, 제한된 색상 팔레트, 8비트/16비트 게임 느낌, 선명한 가장자리
    - **로블록스 스타일**: 블록형 캐릭터, 단순한 텍스처, 밝은 색상, 낮은 디테일
    - **마인크래프트 스타일**: 복셀 기반 디자인, 픽셀화된 텍스처, 직사각형 블록 구조
    - **사이버펑크 스타일**: 네온 색상, 미래 도시 배경, 하이테크와 로우라이프 대비, 디스토피아적 요소
    """)
    
    # 앱 설명
    st.header("사용 방법")
    st.markdown("""
    ### 사용 방법
    1. 사이드바에 OpenAI API 키를 입력합니다.
    2. 스타일 카테고리와 세부 스타일을 선택합니다.
    3. 원하는 4컷 레이아웃을 선택합니다. (A, B, C, D 중 하나)
    4. 웹툰으로 만들고 싶은 스토리를 입력합니다.
    5. 당신의 사진을 업로드합니다. (필수)
    6. 말풍선 스타일을 선택할 수 있습니다.
    7. '웹툰 생성하기' 버튼을 클릭합니다.
    8. 생성된 각 패널의 대화를 수정할 수 있습니다.
    9. '대화 수정 적용' 버튼을 클릭하여 수정사항을 적용합니다.
    10. 생성된 4컷 웹툰을 확인하고 다운로드합니다.
    
    ### 레이아웃 설명
    - **A 레이아웃**: 2x2 그리드 형태로 4개의 패널이 균등하게 배치됩니다.
    - **B 레이아웃**: 세로로 길게 4개의 패널이 순차적으로 배치됩니다.
    - **C 레이아웃**: 상단에 큰 패널 하나, 하단에 작은 패널 2개가 배치됩니다.
    - **D 레이아웃**: 좌측에 세로로 긴 패널, 우측에 작은 패널 2개가 배치됩니다.
    
    ### 한국어 말풍선 팁
    - 대화는 간결하게 작성하는 것이 좋습니다 (20-30자 이내).
    - 한글이 선명하게 표시되도록 적절한 텍스트 크기를 선택하세요.
    - 나레이션은 '(나레이션: 텍스트)'와 같은 형식으로 입력하면 구분됩니다.
    - 감정을 표현하는 음성 효과는 '!' 나 '?' 등을 활용하세요.
    
    ### 참고사항
    - DALL-E 3 API는 생성당 비용이 발생합니다.
    - 이미지 생성에는 시간이 소요될 수 있습니다 (전체 과정에 약 1-2분).
    - 더 좋은 결과를 위해 구체적인 스토리를 제공하세요.
    - 업로드된 사진은 주인공 캐릭터의 특징을 결정하는 데 사용됩니다.
    - 실패한 이미지 생성은 단순화된 프롬프트로 재시도합니다.
    - 품질을 'standard'로 설정하면 API 비용을 절약할 수 있습니다.
    """)
