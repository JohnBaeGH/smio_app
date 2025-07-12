import streamlit as st
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import re
from selenium.webdriver.common.action_chains import ActionChains
import urllib.parse
import os
import sys

# --- 1. URL 정규화 함수 ---
def normalize_naver_place_url(url):
    """
    네이버 플레이스 URL을 메뉴 페이지 URL로 정규화합니다.
    """
    import re
    import requests
    
    # 네이버 공유 링크인 경우 리다이렉트 처리
    if 'naver.me' in url:
        try:
            print(f"네이버 공유 링크 감지: {url}")
            response = requests.head(url, allow_redirects=True, timeout=10)
            final_url = response.url
            print(f"리다이렉트된 URL: {final_url}")
            url = final_url
        except Exception as e:
            print(f"리다이렉트 처리 오류: {e}")
            return None
    
    # URL에서 place ID 추출
    place_id_match = re.search(r'place/(\d+)', url)
    if not place_id_match:
        return None
    
    place_id = place_id_match.group(1)
    
    # 이미 모바일 메뉴 URL인 경우
    if 'm.place.naver.com' in url and '/menu/' in url:
        return url
    
    # 네이버 맵 URL을 모바일 메뉴 URL로 변환
    mobile_menu_url = f"https://m.place.naver.com/restaurant/{place_id}/menu/list?entry=plt"
    return mobile_menu_url

# --- 2. 음료 판단 함수 ---
def is_beverage(menu_name):
    """
    메뉴 이름이 음료인지 판단합니다.
    """
    beverage_keywords = [
        '커피', '아메리카노', '라떼', '카페', '에스프레소', '모카', '카푸치노', '마끼아또',
        '차', '녹차', '홍차', '우롱차', '보리차', '쌍화차', '감잎차', '모과차',
        '주스', '스무디', '에이드', '레몬에이드', '라임에이드', '오렌지에이드',
        '콜라', '사이다', '환타', '스프라이트', '펩시', '코카콜라',
        '우유', '딸기우유', '초코우유', '바나나우유',
        '쉐이크', '밀크쉐이크', '딸기쉐이크', '초코쉐이크',
        '에스프레소', '아이스', '핫', '따뜻한', '차가운',
        '음료', '드링크', '베버리지'
    ]
    
    menu_lower = menu_name.lower()
    return any(keyword in menu_lower for keyword in beverage_keywords)

# --- 3. Chrome WebDriver 설정 함수 ---
def setup_chrome_driver():
    """
    Streamlit Cloud 환경에 최적화된 Chrome WebDriver를 설정합니다.
    """
    options = webdriver.ChromeOptions()
    
    # Streamlit Cloud 환경에서 필수 옵션들
    options.add_argument('--headless')  # 필수: GUI 없이 실행
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-features=VizDisplayCompositor')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-images')
    options.add_argument('--disable-logging')
    options.add_argument('--log-level=3')
    options.add_argument('--silent')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_argument('--disable-ipc-flooding-protection')
    options.add_argument('--remote-debugging-port=9222')
    options.add_argument('--window-size=1920,1080')
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")
    
    # 메모리 사용량 최적화
    options.add_argument('--memory-pressure-off')
    options.add_argument('--max_old_space_size=4096')
    
    try:
        # Streamlit Cloud에서 chromium 사용
        if os.path.exists('/usr/bin/chromium'):
            options.binary_location = '/usr/bin/chromium'
        elif os.path.exists('/usr/bin/chromium-browser'):
            options.binary_location = '/usr/bin/chromium-browser'
        
        # ChromeDriver 설치 및 서비스 생성
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # 타임아웃 설정
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        return driver
        
    except Exception as e:
        print(f"Chrome WebDriver 설정 오류: {e}")
        return None

# --- 4. 웹 스크래핑 기능: 네이버 플레이스에서 정보 가져오기 ---
@st.cache_data(ttl=3600)  # 1시간 캐시
def scrape_restaurant_info(url):
    """
    주어진 네이버 플레이스 URL에서 가게 이름, 메뉴, 주차 정보를 스크래핑합니다.
    """
    driver = None
    try:
        # WebDriver 설정
        driver = setup_chrome_driver()
        if not driver:
            return {"error": "WebDriver 설정에 실패했습니다."}
        
        print(f"URL 접속 시도: {url}")
        driver.get(url)

        # 네이버 플레이스는 iframe 안에 주요 내용이 있으므로, iframe으로 전환해야 합니다.
        print("iframe 찾기 시도...")
        try:
            WebDriverWait(driver, 20).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "entryIframe")))
            print("entryIframe으로 전환 성공")
        except:
            print("entryIframe을 찾을 수 없음, 다른 iframe 시도...")
            try:
                iframe_selectors = [
                    "iframe#entryIframe",
                    "iframe#searchIframe", 
                    "iframe#placeIframe",
                    "iframe[src*='entry']",
                    "iframe[src*='place']"
                ]
                
                iframe_found = False
                for selector in iframe_selectors:
                    try:
                        iframe = driver.find_element(By.CSS_SELECTOR, selector)
                        driver.switch_to.frame(iframe)
                        print(f"iframe 전환 성공: {selector}")
                        iframe_found = True
                        break
                    except:
                        continue
                
                if not iframe_found:
                    print("iframe을 찾을 수 없음, 메인 페이지에서 진행...")
            except Exception as e:
                print(f"iframe 처리 오류: {e}")
                print("메인 페이지에서 진행...")
        
        # 페이지 로딩 대기
        time.sleep(3)
        
        # 메뉴 탭 클릭
        print("메뉴 탭 찾기 및 클릭...")
        menu_tab = None
        for selector in ["a[role='tab']", "a.tpj9w._tab-menu", "a[href*='/menu']", "span.veBoZ", "a._tab-menu"]:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if "메뉴" in element.text:
                        menu_tab = element
                        break
                if menu_tab:
                    break
            except:
                continue
        
        if menu_tab and menu_tab.is_displayed():
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", menu_tab)
            time.sleep(0.5)
            try:
                menu_tab.click()
                time.sleep(2)
                print("메뉴 탭 클릭 성공")
            except:
                print("메뉴 탭 클릭 실패")
        else:
            print("메뉴 탭을 찾을 수 없음")

        # 더보기 버튼 반복 클릭
        print("더보기 버튼 클릭 시작...")
        click_count = 0
        max_clicks = 20  # 클라우드 환경에서는 제한적으로
        
        while click_count < max_clicks:
            more_menu_btn = None
            
            # 더보기 버튼 찾기
            try:
                more_buttons = driver.find_elements(By.CSS_SELECTOR, "span.TeItc")
                for btn in more_buttons:
                    if "더보기" in btn.text:
                        more_menu_btn = btn
                        break
            except:
                pass
            
            if not more_menu_btn:
                try:
                    all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '더보기')]")
                    for element in all_elements:
                        if element.is_displayed() and element.is_enabled():
                            more_menu_btn = element
                            break
                except:
                    pass
            
            if not more_menu_btn:
                print("더보기 버튼이 더 이상 없음 - 모든 메뉴 로드 완료")
                break
            
            print(f"더보기 버튼 {click_count+1}번째 클릭 시도...")
            
            try:
                before_click_count = len(driver.find_elements(By.CSS_SELECTOR, "div.place_section_content ul > li.E2jtL"))
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", more_menu_btn)
                time.sleep(1)
                more_menu_btn.click()
                time.sleep(2)
                
                after_click_count = len(driver.find_elements(By.CSS_SELECTOR, "div.place_section_content ul > li.E2jtL"))
                if after_click_count > before_click_count:
                    print(f"더보기 버튼 {click_count+1}번째 클릭 성공")
                    click_count += 1
                else:
                    break
                    
            except Exception as e:
                print(f"더보기 버튼 클릭 실패: {e}")
                break
        
        # 메뉴 정보 추출
        print("메뉴 정보 추출 시작...")
        time.sleep(2)
        
        current_page_source = driver.page_source
        menu_soup = BeautifulSoup(current_page_source, "html.parser")
        
        menu_items = menu_soup.select("div.place_section_content ul > li.E2jtL")
        print(f"발견된 메뉴 항목 수: {len(menu_items)}")
        
        menu_list = []
        processed_menus = set()
        
        for i, item in enumerate(menu_items):
            # 메뉴 이름 추출
            menu_name = None
            name_selectors = [
                "span.lPzHi",
                "div.yQlqY span",
                "span[class*='name']",
                "div[class*='name'] span",
                "span[class*='title']",
                "div[class*='title'] span",
                "h3", "h4", "h5",
                "div.MXkFw span",
                "div.meDTN span"
            ]
            
            for selector in name_selectors:
                name_tag = item.select_one(selector)
                if name_tag and name_tag.text.strip():
                    menu_name = name_tag.text.strip()
                    break
            
            if not menu_name:
                continue
            
            # 가격 추출
            price = None
            price_selectors = [
                "div.GXS1X em",
                "div.GXS1X",
                "em",
                "span[class*='price']",
                "div[class*='price']"
            ]
            
            for selector in price_selectors:
                price_tag = item.select_one(selector)
                if price_tag:
                    price_text = re.sub(r'[^0-9]', '', price_tag.text)
                    if price_text:
                        try:
                            price = int(price_text)
                            break
                        except ValueError:
                            continue
            
            # 중복 제거
            menu_key = f"{menu_name}_{price}"
            if menu_key not in processed_menus:
                processed_menus.add(menu_key)
                if menu_name:
                    menu_list.append({"name": menu_name, "price": price})

        # 홈 탭에서 기본 정보 추출
        print("홈 탭 정보 추출...")
        address = None
        phone = None
        restaurant_name = None
        restaurant_type = None
        rating = None
        review_visitor = None
        review_blog = None
        short_desc = None
        parking_info = "주차 정보 없음"
        
        # 홈 탭 클릭
        home_tab = None
        home_selectors = ["a[role='tab']", "a.tpj9w._tab-menu", "span.veBoZ"]
        for selector in home_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if "홈" in element.text:
                        home_tab = element
                        break
                if home_tab:
                    break
            except:
                continue
        
        if home_tab and home_tab.is_displayed():
            try:
                home_tab.click()
                time.sleep(2)
                
                home_page = driver.page_source
                home_soup = BeautifulSoup(home_page, "html.parser")
                
                # 기본 정보 추출
                address_tag = home_soup.select_one("span.LDgIH")
                if address_tag:
                    address = address_tag.get_text(strip=True)
                
                phone_tag = home_soup.select_one("span.xlx7Q")
                if phone_tag:
                    phone = phone_tag.get_text(strip=True)
                
                # 가게 이름
                name_tag = home_soup.select_one("div.zD5Nm div.LylZZ.v8v5j span.GHAhO")
                if name_tag:
                    restaurant_name = name_tag.text.strip()
                
                # 업종
                type_tag = home_soup.select_one("div.zD5Nm div.LylZZ.v8v5j span.lnJFt")
                if type_tag:
                    restaurant_type = type_tag.text.strip()
                    
            except Exception as e:
                print(f"홈 탭 정보 추출 오류: {e}")

        return {
            "name": restaurant_name or "가게 이름 정보 없음",
            "type": restaurant_type,
            "rating": rating,
            "review_visitor": review_visitor,
            "review_blog": review_blog,
            "short_desc": short_desc,
            "address": address or "주소 정보 없음",
            "phone": phone or "전화번호 정보 없음",
            "menu": menu_list,
            "parking": parking_info
        }

    except Exception as e:
        print(f"스크래핑 오류 발생: {e}")
        import traceback
        print(f"상세 오류 정보: {traceback.format_exc()}")
        return {"error": f"스크래핑 중 오류가 발생했습니다: {str(e)}"}
    
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

# --- 5. Streamlit UI 구성 ---

# 페이지 기본 설정 - 모바일 최적화
st.set_page_config(
    page_title="Smio | 스마트 팀 주문", 
    page_icon="🍽️", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 모바일 최적화 CSS 스타일링 ---
st.markdown("""
<style>
    /* 모바일 우선 반응형 디자인 */
    .stApp {
        background: #f8fafc;
    }
    
    /* 모바일 뷰포트 설정 */
    @viewport {
        width: device-width;
        initial-scale: 1.0;
        maximum-scale: 1.0;
        user-scalable: no;
    }
    
    /* 메인 컨테이너 - 모바일 최적화 */
    .main-container {
        background: white;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        border: 1px solid #e2e8f0;
    }
    
    /* 헤더 스타일 - 모바일 최적화 */
    .main-header {
        text-align: center;
        padding: 2rem 1rem;
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border-radius: 8px;
        color: white;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        color: #60a5fa;
    }
    
    .main-subtitle {
        font-size: 1rem;
        opacity: 0.9;
        font-weight: 400;
        color: #cbd5e1;
        line-height: 1.4;
    }
    
    /* 카드 스타일 - 모바일 터치 최적화 */
    .feature-card {
        background: white;
        border-radius: 8px;
        padding: 1.25rem;
        margin: 0.75rem 0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
        border: 1px solid #e2e8f0;
        border-left: 3px solid #3b82f6;
        transition: all 0.2s ease;
        -webkit-tap-highlight-color: rgba(59, 130, 246, 0.1);
    }
    
    .feature-card:active {
        transform: scale(0.98);
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
    }
    
    /* 주문 카드 - 모바일 최적화 */
    .order-card {
        background: #1e293b;
        border-radius: 8px;
        padding: 1.25rem;
        margin: 0.75rem 0;
        color: white;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    .status-card {
        background: #0f172a;
        border-radius: 8px;
        padding: 1.25rem;
        margin: 0.75rem 0;
        color: white;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    /* 레스토랑 정보 - 모바일 최적화 */
    .restaurant-info {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border-radius: 8px;
        padding: 1.5rem;
        color: white;
        margin: 0.75rem 0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    .restaurant-name {
        font-size: 1.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
        color: #e2e8f0;
        line-height: 1.3;
    }
    
    .restaurant-detail {
        display: flex;
        align-items: flex-start;
        margin: 0.75rem 0;
        font-size: 0.9rem;
        line-height: 1.4;
    }
    
    .restaurant-detail strong {
        display: block;
        margin-bottom: 0.25rem;
    }
    
    /* 주문 아이템 - 터치 최적화 */
    .order-item {
        background: white;
        border-radius: 6px;
        padding: 1rem;
        margin: 0.5rem 0;
        border: 1px solid #e2e8f0;
        border-left: 3px solid #3b82f6;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        transition: all 0.2s ease;
        -webkit-tap-highlight-color: rgba(59, 130, 246, 0.1);
        min-height: 44px; /* 최소 터치 영역 */
    }
    
    .order-item:active {
        transform: scale(0.98);
        background: #f8fafc;
    }
    
    .order-name {
        font-weight: 600;
        color: #1e293b;
        font-size: 1rem;
        margin-bottom: 0.25rem;
    }
    
    .order-details {
        color: #64748b;
        font-size: 0.85rem;
        line-height: 1.3;
    }
    
    /* 메트릭 카드 - 모바일 최적화 */
    .metric-card {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        border-radius: 8px;
        padding: 1.25rem;
        text-align: center;
        color: white;
        margin: 0.75rem 0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        margin-bottom: 0.25rem;
        line-height: 1.2;
    }
    
    .metric-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    
    /* 최종 주문서 */
    .final-order {
        background: linear-gradient(135deg, #059669 0%, #047857 100%);
        border-radius: 8px;
        padding: 1.5rem;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    .final-order h3 {
        margin-bottom: 1rem;
        font-size: 1.3rem;
        font-weight: 600;
    }
    
    /* 버튼 스타일 - 터치 최적화 */
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        border: none;
        border-radius: 6px;
        padding: 1rem 1.5rem;
        font-weight: 600;
        font-size: 0.95rem;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        transition: all 0.2s ease;
        min-height: 44px; /* 최소 터치 영역 */
        -webkit-tap-highlight-color: rgba(59, 130, 246, 0.3);
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        transform: translateY(-1px);
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.15);
    }
    
    .stButton > button:active {
        transform: translateY(0);
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
    }
    
    /* 입력 필드 - 모바일 키보드 최적화 */
    .stTextInput > div > div > input {
        border-radius: 6px;
        border: 2px solid #d1d5db;
        padding: 1rem;
        font-size: 16px; /* iOS 줌 방지 */
        transition: border-color 0.2s ease;
        background: white;
        min-height: 44px; /* 최소 터치 영역 */
        -webkit-appearance: none;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        outline: none;
    }
    
    /* 선택 박스 - 터치 최적화 */
    .stSelectbox > div > div > select {
        border-radius: 6px;
        border: 2px solid #d1d5db;
        background: white;
        padding: 1rem;
        font-size: 16px; /* iOS 줌 방지 */
        min-height: 44px; /* 최소 터치 영역 */
        -webkit-appearance: none;
    }
    
    /* 숫자 입력 */
    .stNumberInput > div > div > input {
        border-radius: 6px;
        border: 2px solid #d1d5db;
        background: white;
        padding: 1rem;
        font-size: 16px; /* iOS 줌 방지 */
        min-height: 44px; /* 최소 터치 영역 */
    }
    
    /* 폼 스타일 */
    .stForm {
        border: none;
        background: transparent;
    }
    
    /* 확장 가능한 섹션 */
    .streamlit-expanderHeader {
        font-size: 1rem;
        font-weight: 600;
        color: #1e293b;
        padding: 1rem;
        background: #f8fafc;
        border-radius: 6px;
        border: 1px solid #e2e8f0;
        min-height: 44px; /* 최소 터치 영역 */
    }
    
    /* 데이터프레임 모바일 최적화 */
    .stDataFrame {
        border-radius: 6px;
        overflow-x: auto;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        max-width: 100%;
    }
    
    .stDataFrame table {
        font-size: 0.85rem;
    }
    
    /* 스크롤바 스타일 */
    ::-webkit-scrollbar {
        width: 4px;
        height: 4px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f5f9;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #94a3b8;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #64748b;
    }
    
    /* 모바일 전용 스타일 */
    @media (max-width: 768px) {
        .main-title {
            font-size: 2rem;
        }
        
        .main-container {
            margin: 0.25rem;
            padding: 0.75rem;
        }
        
        .restaurant-info {
            padding: 1rem;
        }
        
        .restaurant-name {
            font-size: 1.25rem;
        }
        
        .metric-value {
            font-size: 1.75rem;
        }
        
        /* 컬럼 간격 조정 */
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
        
        /* 그리드 레이아웃을 모바일에서 단일 컬럼으로 */
        .restaurant-info > div {
            display: block !important;
        }
        
        .restaurant-detail {
            margin: 1rem 0;
            padding: 0.75rem;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 6px;
        }
    }
    
    /* 초소형 화면 (320px 이하) */
    @media (max-width: 320px) {
        .main-title {
            font-size: 1.75rem;
        }
        
        .main-subtitle {
            font-size: 0.9rem;
        }
        
        .metric-value {
            font-size: 1.5rem;
        }
        
        .order-item, .feature-card {
            padding: 0.75rem;
        }
    }
    
    /* 터치 제스처 최적화 */
    * {
        -webkit-touch-callout: none;
        -webkit-user-select: none;
        -khtml-user-select: none;
        -moz-user-select: none;
        -ms-user-select: none;
        user-select: none;
    }
    
    input, textarea, select {
        -webkit-user-select: text;
        -khtml-user-select: text;
        -moz-user-select: text;
        -ms-user-select: text;
        user-select: text;
    }
    
    /* iOS Safari 스타일 초기화 */
    input[type="text"], 
    input[type="number"], 
    select, 
    textarea {
        -webkit-appearance: none;
        -moz-appearance: none;
        appearance: none;
        border-radius: 6px;
    }
    
    /* 모바일 키보드로 인한 뷰포트 변경 대응 */
    .stApp {
        min-height: 100vh;
        position: relative;
    }
    
    /* 안전 영역 고려 (iPhone X 이상) */
    @supports(padding: max(0px)) {
        .main-container {
            padding-left: max(1rem, env(safe-area-inset-left));
            padding-right: max(1rem, env(safe-area-inset-right));
        }
    }
</style>
""", unsafe_allow_html=True)

# 세션 상태 초기화
def initialize_session_state():
    """세션 상태를 안전하게 초기화합니다."""
    if 'url_processed' not in st.session_state:
        st.session_state.url_processed = False
    if 'restaurant_info' not in st.session_state:
        st.session_state.restaurant_info = None
    if 'orders' not in st.session_state:
        st.session_state.orders = []
    if 'error_message' not in st.session_state:
        st.session_state.error_message = None

# 세션 상태 초기화 실행
initialize_session_state()

# --- 페이지 1: 랜딩 페이지 (URL 입력 전) ---
if not st.session_state.url_processed:
    
    # 메인 헤더
    st.markdown("""
    <div class="main-header">
        <div class="main-title">Smio</div>
        <div class="main-subtitle">The smartest way to pre-order for your team</div>
        <div style="margin-top: 1rem; font-size: 0.8rem; color: #cbd5e1; opacity: 0.8;">Made by John</div>
    </div>
    """, unsafe_allow_html=True)
    
    # 소개 섹션 - 모바일에서는 단일 컬럼
    if st.container():
        # 데스크톱에서는 2컬럼, 모바일에서는 1컬럼
        is_mobile = st.sidebar.checkbox("모바일 뷰", value=False) # 실제로는 화면 크기로 자동 감지
        
        if True:  # 항상 모바일 친화적으로 표시
            st.markdown("""
            <div class="feature-card">
                <div style="font-size: 2rem; margin-bottom: 1rem;">🚀</div>
                <h3 style="color: #1e293b; margin-bottom: 1rem;">혁신적인 팀 주문 경험</h3>
                <p style="color: #64748b; line-height: 1.6;">
                    점심시간마다 반복되는 복잡한 주문 과정을 혁신적으로 개선했습니다. 
                    더 이상 한 사람이 모든 주문을 받아 정리할 필요가 없어요.
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class="feature-card">
                <div style="font-size: 2rem; margin-bottom: 1rem;">⚡</div>
                <h3 style="color: #1e293b; margin-bottom: 1rem;">실시간 투명한 주문 관리</h3>
                <p style="color: #64748b; line-height: 1.6;">
                    누가 무엇을 주문했는지 실시간으로 확인하고, 
                    자동으로 계산되는 총액과 개인별 금액으로 정산 걱정도 끝.
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class="feature-card" style="background: #1e293b; color: white; border-left: 3px solid #3b82f6;">
                <div style="font-size: 2rem; margin-bottom: 1rem;">✨</div>
                <h3 style="margin-bottom: 1rem; color: #e2e8f0;">핵심 기능</h3>
                <div style="margin: 1rem 0;">
                    <strong style="color: #e2e8f0;">🔗 원클릭 주문방 개설</strong><br>
                    <small style="color: #cbd5e1;">네이버 플레이스 URL만 붙여넣으면 끝</small>
                </div>
                <div style="margin: 1rem 0;">
                    <strong style="color: #e2e8f0;">📱 실시간 주문 현황</strong><br>
                    <small style="color: #cbd5e1;">팀원들의 주문을 실시간으로 확인</small>
                </div>
                <div style="margin: 1rem 0;">
                    <strong style="color: #e2e8f0;">💰 자동 정산 시스템</strong><br>
                    <small style="color: #cbd5e1;">복잡한 계산은 자동으로 처리</small>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # URL 입력 섹션
    st.markdown("""
    <div style="text-align: center; margin: 2rem 0 1.5rem 0;">
        <h2 style="color: #1e293b; margin-bottom: 0.75rem; font-size: 1.5rem;">🎯 지금 바로 시작해보세요!</h2>
        <p style="color: #64748b; font-size: 1rem; line-height: 1.4;">네이버 플레이스 URL을 입력하고 스마트한 팀 주문을 경험해보세요</p>
    </div>
    """, unsafe_allow_html=True)
    
    # URL 입력 폼
    with st.container():
        url_input = st.text_input(
            "네이버 플레이스 URL을 입력하세요", 
            placeholder="예: https://naver.me/FMAxDFTM",
            label_visibility="collapsed",
            key="url_input",
            help="네이버 지도나 플레이스 링크를 붙여넣으세요"
        )
        
        # 모바일에서는 전체 너비로 버튼 표시
        if st.button("🚀 주문방 만들기", type="primary", use_container_width=True):
            if not url_input:
                st.warning("⚠️ URL을 입력해주세요.")
            else:
                with st.spinner("🔍 가게 정보를 불러오는 중입니다... (최대 1분 소요)"):
                    try:
                        normalized_url = normalize_naver_place_url(url_input)
                        if not normalized_url:
                            st.error("❌ 올바른 네이버 플레이스 URL 형식이 아닙니다.")
                        else:
                            restaurant_data = scrape_restaurant_info(normalized_url)
                            
                            if restaurant_data and "error" in restaurant_data:
                                st.error(f"❌ {restaurant_data['error']}")
                            elif restaurant_data and restaurant_data.get("menu"):
                                st.session_state.restaurant_info = restaurant_data
                                st.session_state.url_processed = True
                                st.session_state.orders = []
                                st.session_state.error_message = None
                                st.success("✅ 주문방이 성공적으로 생성되었습니다!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("❌ 메뉴 정보를 가져오는 데 실패했습니다. URL을 확인하시거나 다른 가게를 시도해주세요.")
                                
                    except Exception as e:
                        print(f"예상치 못한 오류: {e}")
                        st.error("❌ 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")

# --- 페이지 2: 주문 및 현황 페이지 (URL 입력 후) ---
if st.session_state.url_processed:
    info = st.session_state.restaurant_info
    
    # 에러 체크
    if "error" in info:
        st.error(f"❌ {info['error']}")
        if st.button("🔄 새로운 주문방 만들기", use_container_width=True):
            st.session_state.url_processed = False
            st.session_state.restaurant_info = None
            st.session_state.orders = []
            st.rerun()
        st.stop()
    
    # 레스토랑 정보 헤더
    st.markdown(f"""
    <div class="restaurant-info">
        <div class="restaurant-name">🍽️ {info.get('name', '가게 이름 정보 없음')}</div>
        <div>
            <div class="restaurant-detail">
                <span style="margin-right: 0.75rem;">📍</span>
                <div>
                    <strong>주소</strong><br>
                    <span style="font-size: 0.85rem; line-height: 1.3;">{info.get('address', '정보 없음')}</span>
                </div>
            </div>
            <div class="restaurant-detail">
                <span style="margin-right: 0.75rem;">📞</span>
                <div>
                    <strong>전화번호</strong><br>
                    <span style="font-size: 0.85rem;">{info.get('phone', '정보 없음')}</span>
                </div>
            </div>
            <div class="restaurant-detail">
                <span style="margin-right: 0.75rem;">🚗</span>
                <div>
                    <strong>주차정보</strong><br>
                    <span style="font-size: 0.85rem;">{info.get('parking', '정보 없음')}</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 메인 주문 섹션 - 모바일에서는 세로 배치
    col1, col2 = st.columns([1, 1], gap="medium")
    
    with col1:
        st.markdown("""
        <div class="order-card">
            <h3 style="margin-bottom: 1rem; font-size: 1.2rem;">✍️ 메뉴 담기</h3>
        </div>
        """, unsafe_allow_html=True)
        
        if not info.get("menu"):
            st.warning("⚠️ 메뉴 정보를 불러올 수 없습니다. 다른 식당을 시도해보세요.")
        else:
            with st.form("order_form", clear_on_submit=True):
                menu_names = []
                for item in info["menu"]:
                    price_str = f"{item['price']:,}원" if item.get('price') is not None else "가격 정보 없음"
                    menu_names.append(f"{item['name']} ({price_str})")
                
                participant_name = st.text_input(
                    "👤 주문자 이름", 
                    key="participant_name_input",
                    placeholder="이름을 입력하세요"
                )
                
                selected_menu_str = st.selectbox(
                    "🍽️ 메뉴 선택", 
                    menu_names,
                    help="메뉴를 선택해주세요"
                )
                
                quantity = st.number_input(
                    "📊 수량", 
                    min_value=1, 
                    value=1,
                    help="주문할 수량을 입력하세요"
                )
                
                if selected_menu_str in menu_names:
                    selected_index = menu_names.index(selected_menu_str)
                    selected_menu_info = info["menu"][selected_index]
                    selected_menu_name = selected_menu_info["name"]
                    
                    beverage_options = None
                    special_request = None
                    if is_beverage(selected_menu_name):
                        beverage_options = st.selectbox(
                            "🧊 음료 옵션", 
                            ["(선택)", "Hot", "Ice"], 
                            key="beverage_options",
                            help="음료 온도를 선택하세요"
                        )
                        special_request = st.text_input(
                            "📝 특별 요청사항", 
                            placeholder="예: 샷 추가, 시럽 1번만", 
                            key="special_request",
                            help="특별한 요청사항이 있으면 입력하세요"
                        )
                    
                    submitted = st.form_submit_button(
                        "🛒 주문 추가하기", 
                        type="primary", 
                        use_container_width=True
                    )

                    if submitted:
                        if not participant_name.strip():
                            st.warning("⚠️ 주문자 이름을 입력해주세요!")
                        else:
                            price = selected_menu_info.get("price", 0) or 0
                            order_info = {
                                "name": participant_name.strip(),
                                "menu": selected_menu_name,
                                "quantity": quantity,
                                "price": price * quantity,
                                "beverage_option": beverage_options if beverage_options and beverage_options != "(선택)" else None,
                                "special_request": special_request.strip() if special_request else None
                            }
                            st.session_state.orders.append(order_info)
                            st.success(f"✅ {participant_name.strip()}님의 주문이 추가되었습니다!")
                            time.sleep(1)
                            st.rerun()
    
    with col2:
        st.markdown("""
        <div class="status-card">
            <h3 style="margin-bottom: 1rem; font-size: 1.2rem;">📊 실시간 주문 현황</h3>
        </div>
        """, unsafe_allow_html=True)
        
        if not st.session_state.orders:
            st.markdown("""
            <div style="text-align: center; padding: 1.5rem; background: white; border-radius: 8px; margin: 0.75rem 0; border: 1px solid #e2e8f0;">
                <div style="font-size: 3rem; margin-bottom: 0.75rem;">🛒</div>
                <h4 style="color: #64748b; font-size: 1rem;">아직 주문이 없습니다</h4>
                <p style="color: #94a3b8; font-size: 0.9rem;">왼쪽에서 메뉴를 담아주세요!</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            orders_df = pd.DataFrame(st.session_state.orders)
            total_price = orders_df['price'].sum()
            
            # 총액 표시
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{total_price:,.0f}원</div>
                <div class="metric-label">현재 총 주문 금액</div>
            </div>
            """, unsafe_allow_html=True)
            
            # 주문 목록
            st.markdown("**📋 주문 목록**")
            for i, order in enumerate(st.session_state.orders):
                details = []
                if order.get('beverage_option'):
                    details.append(order['beverage_option'])
                if order.get('special_request'):
                    details.append(f"요청: {order['special_request']}")
                
                details_text = f"<br><small style='color: #94a3b8;'>{' / '.join(details)}</small>" if details else ""
                
                st.markdown(f"""
                <div class="order-item">
                    <div class="order-name">{order['name']}</div>
                    <div class="order-details">{order['menu']} × {order['quantity']}개 | {order['price']:,}원{details_text}</div>
                </div>
                """, unsafe_allow_html=True)
            
            # 주문 관리
            with st.expander("🔧 주문 수정/삭제"):
                if st.session_state.orders:
                    def format_order_for_deletion(i):
                        order = st.session_state.orders[i]
                        return f"{i+1}. {order['name']} - {order['menu']} ({order['quantity']}개)"
                    
                    order_to_delete_index = st.selectbox(
                        "삭제할 주문을 선택하세요", 
                        options=range(len(st.session_state.orders)),
                        format_func=format_order_for_deletion,
                        index=None,
                        placeholder="삭제할 주문 선택"
                    )
                    
                    if st.button("🗑️ 선택한 주문 삭제", use_container_width=True):
                        if order_to_delete_index is not None:
                            deleted_order = st.session_state.orders.pop(order_to_delete_index)
                            st.success(f"✅ {deleted_order['name']}님의 주문이 삭제되었습니다!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("⚠️ 삭제할 주문을 먼저 선택해주세요.")
    
    # 최종 주문서
    if st.session_state.orders:
        with st.expander("📋 최종 주문서 보기 (주문 총무용)", expanded=False):
            orders_df = pd.DataFrame(st.session_state.orders)
            
            st.markdown("""
            <div class="final-order">
                <h3>✅ 최종 주문서</h3>
            </div>
            """, unsafe_allow_html=True)
            
            # 메뉴별 요약
            st.markdown("### 🧮 메뉴별 주문 합계")
            menu_summary = orders_df.groupby("menu").agg(
                총_수량=('quantity', 'sum'),
                주문자=('name', lambda x: ', '.join(x.unique()))
            ).reset_index()
            
            st.dataframe(
                menu_summary, 
                use_container_width=True,
                hide_index=True
            )
            
            # 개인별 상세 내역
            st.markdown("### 🧑‍💻 개인별 상세 내역")
            person_summary = orders_df.groupby("name").agg(총액=('price', 'sum')).reset_index()
            
            for _, row in person_summary.iterrows():
                with st.container():
                    st.markdown(f"""
                    <div class="order-item">
                        <div class="order-name">{row['name']}</div>
                        <div class="order-details">총 주문 금액: {row['총액']:,}원</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    person_orders = orders_df[orders_df['name'] == row['name']]
                    for _, p_order in person_orders.iterrows():
                        details = []
                        if 'beverage_option' in p_order and pd.notna(p_order['beverage_option']):
                            details.append(p_order['beverage_option'])
                        if 'special_request' in p_order and pd.notna(p_order['special_request']):
                            details.append(f"요청: {p_order['special_request']}")
                        
                        details_text = f"<br><small style='color: #94a3b8;'>{' / '.join(details)}</small>" if details else ""
                        
                        st.markdown(f"""
                        <div style="margin-left: 1rem; color: #64748b; margin-bottom: 0.5rem; padding: 0.5rem; background: #f8fafc; border-radius: 4px; font-size: 0.9rem;">
                            • {p_order['menu']}: {p_order['quantity']}개 ({p_order['price']:,}원){details_text}
                        </div>
                        """, unsafe_allow_html=True)
            
            # 최종 합계
            grand_total = orders_df['price'].sum()
            st.markdown(f"""
            <div class="final-order" style="text-align: center; margin-top: 1.5rem; background: linear-gradient(135deg, #059669 0%, #047857 100%);">
                <h2 style="margin: 0; color: white; font-size: 1.5rem;">💰 총 합계: {grand_total:,}원</h2>
            </div>
            """, unsafe_allow_html=True)
    
    # 새로운 주문방 만들기
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 새로운 주문방 만들기", use_container_width=True):
        st.session_state.url_processed = False
        st.session_state.restaurant_info = None
        st.session_state.orders = []
        st.rerun()