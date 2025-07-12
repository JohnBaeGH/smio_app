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

# --- 3. 웹 스크래핑 기능: 네이버 플레이스에서 정보 가져오기 ---
@st.cache_data
def scrape_restaurant_info(url):
    """
    주어진 네이버 플레이스 URL에서 가게 이름, 메뉴, 주차 정보를 스크래핑합니다.
    """
    options = webdriver.ChromeOptions()
    
    # Streamlit Cloud용 Chrome 옵션 설정
    options.add_argument('--headless')  # Streamlit Cloud에서 필수
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
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-blink-features')
    options.add_argument('--remote-debugging-port=9222')
    options.add_argument('--single-process')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("user-agent=Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Mobile Safari/537.36")
    
    # Streamlit Cloud에서 ChromeDriver 경로 설정
    options.binary_location = "/usr/bin/chromium-browser"

    try:
        # Streamlit Cloud용 ChromeDriver 설정
        try:
            # 먼저 시스템 chromedriver 시도
            service = Service("/usr/bin/chromedriver")
            driver = webdriver.Chrome(service=service, options=options)
            print("시스템 chromedriver 사용 성공")
        except Exception as e1:
            print(f"시스템 chromedriver 실패: {e1}")
            try:
                # chromium-chromedriver 시도
                service = Service("/usr/bin/chromium-chromedriver")
                driver = webdriver.Chrome(service=service, options=options)
                print("chromium-chromedriver 사용 성공")
            except Exception as e2:
                print(f"chromium-chromedriver 실패: {e2}")
                try:
                    # webdriver-manager로 자동 설치 시도
                    service = Service(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=options)
                    print("webdriver-manager 사용 성공")
                except Exception as e3:
                    print(f"모든 ChromeDriver 시도 실패: {e3}")
                    raise Exception("ChromeDriver를 찾을 수 없습니다.")
        
        driver.get(url)

        # 네이버 플레이스는 iframe 안에 주요 내용이 있으므로, iframe으로 전환해야 합니다.
        # WebDriverWait를 사용하여 iframe이 로드될 때까지 최대 20초간 기다립니다.
        print("iframe 찾기 시도...")
        try:
            WebDriverWait(driver, 20).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "entryIframe")))
            print("entryIframe으로 전환 성공")
        except:
            print("entryIframe을 찾을 수 없음, 다른 iframe 시도...")
            try:
                # 다른 iframe ID들 시도
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
        
        # 메뉴 탭이 클릭 가능할 때까지 기다립니다 (페이지 로딩 확인용)
        print("메뉴 탭 로딩 대기...")
        try:
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='/menu']")))
            print("메뉴 탭 로딩 완료")
        except:
            print("메뉴 탭을 찾을 수 없음, 다른 방법 시도...")
            try:
                # 다른 메뉴 탭 선택자들 시도
                menu_selectors = [
                    "a[href*='/menu']",
                    "a._tab-menu",
                    "span.veBoZ",
                    "a[role='tab']"
                ]
                
                menu_found = False
                for selector in menu_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            if "메뉴" in element.text:
                                print(f"메뉴 탭 발견: {selector}")
                                menu_found = True
                                break
                        if menu_found:
                            break
                    except:
                        continue
                
                if not menu_found:
                    print("메뉴 탭을 찾을 수 없음, 계속 진행...")
            except Exception as e:
                print(f"메뉴 탭 찾기 오류: {e}")

        # 여러 종류의 팝업/가림막이 있으면 모두 사라질 때까지 대기 (최대 10초)
        popup_selectors = [
            ".StyledToast-sc-vur252-0",  # 기존 토스트
            ".ToastContainer", ".Toastify",  # 토스트 라이브러리류
            ".modal", ".layer", ".dimmed",  # 모달/가림막
            "div[role='status']",  # 접근성 토스트
        ]
        try:
            WebDriverWait(driver, 10).until(
                lambda d: all(
                    len(d.find_elements(By.CSS_SELECTOR, sel)) == 0 for sel in popup_selectors
                )
            )
        except:
            pass  # 10초 후에도 남아있으면 그냥 진행

        # --- 메뉴 탭 먼저 클릭 ---
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

        # --- 더보기 버튼 반복 클릭 (개선된 방식) ---
        print("더보기 버튼 클릭 시작...")
        
        # 클릭 전 메뉴 개수 확인
        initial_menu_count = len(driver.find_elements(By.CSS_SELECTOR, "div.place_section_content ul > li.E2jtL"))
        print(f"초기 메뉴 개수: {initial_menu_count}")
        
        # 더보기 버튼이 없을 때까지 계속 클릭
        click_count = 0
        max_clicks = 50  # 최대 50번 시도 (안전장치)
        
        while click_count < max_clicks:
            # 더보기 버튼 찾기 (여러 방법 시도)
            more_menu_btn = None
            
            # 방법 1: span.TeItc 클래스로 찾기
            try:
                more_buttons = driver.find_elements(By.CSS_SELECTOR, "span.TeItc")
                for btn in more_buttons:
                    if "더보기" in btn.text:
                        more_menu_btn = btn
                        print("span.TeItc로 더보기 버튼 발견")
                        break
            except Exception as e:
                print(f"span.TeItc 검색 실패: {e}")
            
            # 방법 2: SVG 아이콘을 포함하는 더보기 버튼 찾기
            if not more_menu_btn:
                try:
                    svg_elements = driver.find_elements(By.CSS_SELECTOR, "svg.E4qxG")
                    for svg in svg_elements:
                        parent = svg.find_element(By.XPATH, "./..")
                        if "더보기" in parent.text:
                            more_menu_btn = parent
                            print("SVG 아이콘 기반 더보기 버튼 발견")
                            break
                except Exception as e:
                    print(f"SVG 아이콘 검색 실패: {e}")
            
            # 방법 3: 텍스트 기반 검색
            if not more_menu_btn:
                try:
                    all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '더보기')]")
                    for element in all_elements:
                        if element.is_displayed() and element.is_enabled():
                            more_menu_btn = element
                            print("텍스트 기반 더보기 버튼 발견")
                            break
                except Exception as e:
                    print(f"텍스트 기반 검색 실패: {e}")
            
            # 더보기 버튼이 없으면 종료
            if not more_menu_btn:
                print("더보기 버튼이 더 이상 없음 - 모든 메뉴 로드 완료")
                break
            
            print(f"더보기 버튼 {click_count+1}번째 클릭 시도...")
            
            try:
                # 버튼이 화면에 보이도록 스크롤
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", more_menu_btn)
                time.sleep(1)
                
                # 클릭 전 메뉴 개수 확인
                before_click_count = len(driver.find_elements(By.CSS_SELECTOR, "div.place_section_content ul > li.E2jtL"))
                
                # 클릭 시도
                more_menu_btn.click()
                time.sleep(3)  # 클릭 후 대기 시간 증가
                
                # 메뉴가 로드될 때까지 대기 (최대 10초)
                wait_time = 0
                while wait_time < 10:
                    time.sleep(1)
                    after_click_count = len(driver.find_elements(By.CSS_SELECTOR, "div.place_section_content ul > li.E2jtL"))
                    if after_click_count > before_click_count:
                        print(f"더보기 버튼 {click_count+1}번째 클릭 성공 - 메뉴 {before_click_count}개 → {after_click_count}개")
                        click_count += 1
                        break
                    wait_time += 1
                else:
                    print(f"더보기 버튼 {click_count+1}번째 클릭 후 메뉴 로드 대기 시간 초과")
                    # 더보기 버튼이 여전히 있는지 확인
                    try:
                        still_more_btn = driver.find_elements(By.CSS_SELECTOR, "span.TeItc")
                        has_more = False
                        for btn in still_more_btn:
                            if "더보기" in btn.text:
                                has_more = True
                                break
                        if not has_more:
                            print("더보기 버튼이 더 이상 없음 - 모든 메뉴 로드 완료")
                            break
                    except:
                        break
                    
            except Exception as e:
                print(f"더보기 버튼 클릭 실패: {e}")
                # JavaScript로 클릭 시도
                try:
                    before_click_count = len(driver.find_elements(By.CSS_SELECTOR, "div.place_section_content ul > li.E2jtL"))
                    driver.execute_script("arguments[0].click();", more_menu_btn)
                    time.sleep(3)
                    
                    # 메뉴가 로드될 때까지 대기
                    wait_time = 0
                    while wait_time < 10:
                        time.sleep(1)
                        after_click_count = len(driver.find_elements(By.CSS_SELECTOR, "div.place_section_content ul > li.E2jtL"))
                        if after_click_count > before_click_count:
                            print(f"JavaScript로 더보기 버튼 {click_count+1}번째 클릭 성공 - 메뉴 {before_click_count}개 → {after_click_count}개")
                            click_count += 1
                            break
                        wait_time += 1
                    else:
                        print(f"JavaScript 클릭 후 메뉴 로드 대기 시간 초과")
                        break
                except Exception as e2:
                    print(f"JavaScript 클릭도 실패: {e2}")
                    break
        
        # 최종 메뉴 개수 확인
        final_menu_count = len(driver.find_elements(By.CSS_SELECTOR, "div.place_section_content ul > li.E2jtL"))
        print(f"최종 메뉴 개수: {final_menu_count} (초기: {initial_menu_count}개, 총 {click_count}번 클릭)")

        # ★★★ 핵심 수정: 더보기 버튼 클릭 완료 후 현재 상태에서 바로 메뉴 정보 추출 ★★★
        print("더보기 클릭 완료 후 메뉴 정보 추출 시작...")
        time.sleep(2)  # 안정화 대기
        
        # 현재 페이지에서 메뉴 정보 추출
        current_page_source = driver.page_source
        menu_soup = BeautifulSoup(current_page_source, "html.parser")
        
        # 메뉴 추출 로직
        print("메뉴 정보 추출 시작...")
        menu_items = menu_soup.select("div.place_section_content ul > li.E2jtL")
        print(f"발견된 메뉴 항목 수: {len(menu_items)}")
        
        # 메뉴 리스트 초기화
        menu_list = []
        
        # 중복 제거를 위한 set
        processed_menus = set()
        
        for i, item in enumerate(menu_items):
            # 메뉴 이름 추출 (다양한 선택자 시도)
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
                print(f"메뉴 항목 {i+1}에서 이름을 찾을 수 없음")
                continue
            
            # 가격 추출 (다양한 선택자 시도)
            price = None
            price_selectors = [
                "div.GXS1X em",
                "div.GXS1X",
                "em",
                "span[class*='price']",
                "div[class*='price']",
                "span[class*='cost']",
                "div[class*='cost']"
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
                    print(f"메뉴 추가: {menu_name} - {price}원" if price else f"메뉴 추가: {menu_name} - 가격 정보 없음")
        
        print(f"총 {len(menu_list)}개의 메뉴를 찾았습니다.")

        # --- 1. 홈 탭 클릭 및 정보 추출 ---
        print("홈 탭 찾기 시작...")
        address = None
        phone = None
        restaurant_name = None
        restaurant_type = None
        rating = None
        review_visitor = None
        review_blog = None
        short_desc = None
        home_tab = None
        home_selectors = [
            "a[role='tab']",
            "a.tpj9w._tab-menu",
            "a[href*='/home']",
            "span.veBoZ",
            "a._tab-menu",
        ]
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
        if not home_tab:
            try:
                home_tab = driver.execute_script("""
                    return document.querySelector('a[role=\"tab\"]') || 
                           document.querySelector('a.tpj9w._tab-menu') ||
                           document.querySelector('a[href*=\"/home\"]') ||
                           document.querySelector('span.veBoZ') ||
                           Array.from(document.querySelectorAll('*')).find(el => el.textContent.includes('홈'));
                """)
            except:
                pass
        if home_tab and home_tab.is_displayed():
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", home_tab)
            home_tab.click()
            WebDriverWait(driver, 10).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, "span.LDgIH") or d.find_elements(By.CSS_SELECTOR, "span.xlx7Q")
            )
            time.sleep(1)
            home_page = driver.page_source
            home_soup = BeautifulSoup(home_page, "html.parser")
            # 주소/전화번호
            address_tag = home_soup.select_one("span.LDgIH")
            if address_tag:
                address = address_tag.get_text(strip=True)
            phone_tag = home_soup.select_one("span.xlx7Q")
            if phone_tag:
                phone = phone_tag.get_text(strip=True)
            # 가게 이름, 업종, 평점, 리뷰, 한줄평
            title_wrap = home_soup.select_one("div.zD5Nm div.LylZZ.v8v5j")
            if title_wrap:
                name_tag = title_wrap.select_one("span.GHAhO")
                if name_tag:
                    restaurant_name = name_tag.text.strip()
                type_tag = title_wrap.select_one("span.lnJFt")
                if type_tag:
                    restaurant_type = type_tag.text.strip()
            info_wrap = home_soup.select_one("div.zD5Nm div.dAsGb")
            if info_wrap:
                rating_tag = info_wrap.select_one("span.PXMot.LXIwF")
                if rating_tag:
                    rating = rating_tag.get_text(strip=True).replace("별점", "").strip()
                review_tags = info_wrap.select("span.PXMot > a")
                if review_tags and len(review_tags) >= 2:
                    review_visitor = review_tags[0].get_text(strip=True)
                    review_blog = review_tags[1].get_text(strip=True)
                desc_tag = info_wrap.select_one("div.XtBbS")
                if desc_tag:
                    short_desc = desc_tag.get_text(strip=True)
        else:
            print("홈 탭을 찾을 수 없거나 클릭할 수 없습니다")

        # --- 3. 정보 탭 클릭 및 정보 추출 ---
        print("정보 탭 찾기 시작...")
        info_tab = None
        for selector in ["a[role='tab']", "a.tpj9w._tab-menu", "a[href*='/information']", "span.veBoZ", "a._tab-menu"]:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if "정보" in element.text:
                        info_tab = element
                        break
                if info_tab:
                    break
            except:
                continue
        if not info_tab:
            try:
                info_tab = driver.execute_script("""
                    return document.querySelector('a[role=\"tab\"]') || 
                           document.querySelector('a.tpj9w._tab-menu') ||
                           document.querySelector('a[href*=\"/information\"]') ||
                           document.querySelector('span.veBoZ') ||
                           Array.from(document.querySelectorAll('*')).find(el => el.textContent.includes('정보'));
                """)
            except:
                pass
        parking_info = "주차 정보 없음"
        if info_tab and info_tab.is_displayed():
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", info_tab)
            info_tab.click()
            time.sleep(1)
            info_page = driver.page_source
            info_soup = BeautifulSoup(info_page, "html.parser")
            try:
                status_tag = info_soup.select_one("div.SGJcE div.uWPF_ div.qbROU div.TZ6eS")
                parking_status = status_tag.get_text(strip=True) if status_tag else None
                parking_type = None
                if status_tag:
                    blind = status_tag.select_one("span.place_blind")
                    if blind:
                        parking_type = blind.get_text(strip=True)
                detail_tag = info_soup.select_one("div.MStrC span.zPfVt")
                parking_detail = detail_tag.get_text(strip=True) if detail_tag else None
                parking_info = ""
                if parking_status:
                    parking_info += parking_status
                if parking_type:
                    parking_info += f" ({parking_type})"
                if parking_detail:
                    parking_info += f"\n상세: {parking_detail}"
                if not parking_info:
                    parking_info = "주차 정보 없음"
            except Exception as e:
                print(f"주차 정보 추출 오류: {e}")
        else:
            print("정보 탭을 찾을 수 없거나 클릭할 수 없습니다")

        return {
            "name": restaurant_name,
            "type": restaurant_type,
            "rating": rating,
            "review_visitor": review_visitor,
            "review_blog": review_blog,
            "short_desc": short_desc,
            "address": address,
            "phone": phone,
            "menu": menu_list,
            "parking": parking_info
        }

    except Exception as e:
        print(f"스크래핑 오류 발생: {e}")
        import traceback
        print(f"상세 오류 정보: {traceback.format_exc()}")
        return None
    finally:
        if 'driver' in locals():
            driver.quit()

# --- 4. Streamlit UI 구성 ---

# 페이지 기본 설정
st.set_page_config(
    page_title="Smio | 스마트 팀 주문", 
    page_icon="🍽️", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 전문적인 CSS 스타일링 (모바일 최적화) ---
st.markdown("""
<style>
    /* 전체 배경 및 기본 설정 */
    .stApp {
        background: #f8fafc;
    }
    
    /* 모바일 전용 글로벌 설정 */
    @media (max-width: 768px) {
        .main .block-container {
            padding-top: 1rem;
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 100%;
        }
        
        .stButton > button {
            width: 100% !important;
            padding: 1rem !important;
            font-size: 1.1rem !important;
            margin: 0.5rem 0 !important;
        }
        
        .stTextInput > div > div > input {
            font-size: 16px !important; /* iOS 줌 방지 */
            padding: 1rem !important;
            height: auto !important;
            min-height: 50px !important;
        }
        
        .stSelectbox > div > div {
            font-size: 16px !important;
        }
        
        .stNumberInput > div > div > input {
            font-size: 16px !important;
            padding: 1rem !important;
        }
    }
    
    /* 메인 컨테이너 */
    .main-container {
        background: white;
        border-radius: 12px;
        padding: 2rem;
        margin: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border: 1px solid #e2e8f0;
    }
    
    /* 헤더 스타일 */
    .main-header {
        text-align: center;
        padding: 2rem 1rem;
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border-radius: 12px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        color: #3b82f6;
    }
    
    .main-subtitle {
        font-size: 1.1rem;
        opacity: 0.9;
        font-weight: 400;
        color: #cbd5e1;
        margin-bottom: 1rem;
    }
    
    /* 카드 스타일 */
    .feature-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        border: 1px solid #e2e8f0;
        border-left: 4px solid #3b82f6;
        transition: all 0.3s ease;
    }
    
    .feature-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px -5px rgba(0, 0, 0, 0.1);
        border-left-color: #2563eb;
    }
    
    .feature-icon {
        font-size: 2rem;
        margin-bottom: 1rem;
    }
    
    /* 주문 카드 */
    .order-card {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        color: white;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .status-card {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        color: white;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    /* 메트릭 카드 */
    .metric-card {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .metric-value {
        font-size: 2.2rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    
    .metric-label {
        font-size: 1rem;
        opacity: 0.9;
    }
    
    /* 버튼 스타일 (모바일 최적화) */
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 1rem 2rem;
        font-weight: 600;
        font-size: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
        min-height: 50px;
        width: 100%;
        cursor: pointer;
        touch-action: manipulation; /* 모바일 터치 최적화 */
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        transform: translateY(-2px);
        box-shadow: 0 6px 12px -2px rgba(0, 0, 0, 0.15);
    }
    
    .stButton > button:active {
        transform: translateY(0);
    }
    
    /* 입력 필드 스타일 (모바일 최적화) */
    .stTextInput > div > div > input {
        border-radius: 12px;
        border: 2px solid #d1d5db;
        padding: 1rem;
        font-size: 16px; /* iOS 줌 방지 */
        transition: all 0.3s ease;
        background: white;
        min-height: 50px;
        -webkit-appearance: none; /* iOS 스타일 제거 */
        appearance: none;
        box-sizing: border-box;
        width: 100%;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        outline: none;
        transform: scale(1.02);
    }
    
    .stTextInput > div > div > input::placeholder {
        color: #9ca3af;
        opacity: 1;
    }
    
    /* 선택 박스 스타일 (모바일 최적화) */
    .stSelectbox > div > div > select {
        border-radius: 12px;
        border: 2px solid #d1d5db;
        background: white;
        padding: 1rem;
        font-size: 16px;
        min-height: 50px;
        -webkit-appearance: none;
        appearance: none;
    }
    
    .stSelectbox > div > div > select:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        outline: none;
    }
    
    /* 숫자 입력 스타일 */
    .stNumberInput > div > div > input {
        border-radius: 12px;
        border: 2px solid #d1d5db;
        background: white;
        padding: 1rem;
        font-size: 16px;
        min-height: 50px;
    }
    
    /* 정보 박스 스타일 */
    .restaurant-info {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border-radius: 12px;
        padding: 2rem;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .restaurant-name {
        font-size: 1.8rem;
        font-weight: bold;
        margin-bottom: 1.5rem;
        color: #e2e8f0;
        line-height: 1.3;
    }
    
    .restaurant-detail {
        display: flex;
        align-items: flex-start;
        margin: 1rem 0;
        font-size: 0.95rem;
        line-height: 1.4;
    }
    
    .restaurant-detail span {
        margin-right: 0.75rem;
        min-width: 20px;
        flex-shrink: 0;
    }
    
    /* 주문 아이템 스타일 */
    .order-item {
        background: white;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.75rem 0;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #3b82f6;
        box-shadow: 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: all 0.2s ease;
    }
    
    .order-item:hover {
        box-shadow: 0 4px 8px -2px rgba(0, 0, 0, 0.1);
    }
    
    .order-name {
        font-weight: 600;
        color: #1e293b;
        font-size: 1.1rem;
        margin-bottom: 0.25rem;
    }
    
    .order-details {
        color: #64748b;
        font-size: 0.9rem;
        line-height: 1.4;
    }
    
    /* 최종 주문서 스타일 */
    .final-order {
        background: linear-gradient(135deg, #059669 0%, #047857 100%);
        border-radius: 12px;
        padding: 2rem;
        color: white;
        margin: 2rem 0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .final-order h3 {
        margin-bottom: 1rem;
        font-size: 1.6rem;
        font-weight: 600;
    }
    
    /* URL 입력 섹션 강화 */
    .url-input-section {
        background: white;
        border-radius: 16px;
        padding: 2rem;
        margin: 2rem 0;
        box-shadow: 0 8px 25px -5px rgba(0, 0, 0, 0.1);
        border: 1px solid #e2e8f0;
    }
    
    /* 애니메이션 */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .fade-in {
        animation: fadeIn 0.6s ease-out;
    }
    
    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
    }
    
    .pulse {
        animation: pulse 2s infinite;
    }
    
    /* 스크롤바 스타일 */
    ::-webkit-scrollbar {
        width: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f5f9;
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #94a3b8;
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #64748b;
    }
    
    /* 모바일 반응형 디자인 강화 */
    @media (max-width: 768px) {
        .main-title {
            font-size: 2rem;
        }
        
        .main-subtitle {
            font-size: 1rem;
        }
        
        .main-container {
            margin: 0.5rem;
            padding: 1rem;
        }
        
        .restaurant-info {
            padding: 1.5rem;
        }
        
        .restaurant-name {
            font-size: 1.5rem;
        }
        
        .restaurant-detail {
            font-size: 0.9rem;
            margin: 0.75rem 0;
        }
        
        .feature-card {
            margin: 0.75rem 0;
            padding: 1.25rem;
        }
        
        .feature-card h3 {
            font-size: 1.1rem;
        }
        
        .feature-card p {
            font-size: 0.9rem;
        }
        
        .order-card, .status-card {
            padding: 1.25rem;
            margin: 0.75rem 0;
        }
        
        .metric-value {
            font-size: 1.8rem;
        }
        
        .url-input-section {
            padding: 1.5rem;
            margin: 1rem 0;
        }
        
        /* 모바일에서 컬럼을 세로로 배치 */
        .element-container .row-widget {
            flex-direction: column !important;
        }
        
        .element-container .column {
            width: 100% !important;
            margin-bottom: 1rem;
        }
    }
    
    /* 작은 모바일 화면 (360px 이하) */
    @media (max-width: 360px) {
        .main-header {
            padding: 1.5rem 0.75rem;
        }
        
        .main-title {
            font-size: 1.75rem;
        }
        
        .restaurant-info, .feature-card, .order-card, .status-card {
            padding: 1rem;
        }
        
        .url-input-section {
            padding: 1rem;
        }
    }
    
    /* Streamlit 기본 스타일 오버라이드 */
    .stSelectbox > div > div > div {
        background-color: white;
    }
    
    /* 폼 요소 강화 */
    .stForm {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    
    /* 테이블 스타일 */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    
    /* 익스팬더 스타일 */
    .streamlit-expanderHeader {
        font-weight: 600;
        font-size: 1.1rem;
    }
    
    /* 알림 메시지 강화 */
    .stAlert {
        border-radius: 12px;
        border: none;
        padding: 1rem 1.5rem;
    }
    
    /* 터치 피드백 */
    .stButton > button:active,
    .order-item:active,
    .feature-card:active {
        transform: scale(0.98);
        transition: transform 0.1s ease;
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
    <div class="main-header fade-in">
        <div class="main-title">Smio</div>
        <div class="main-subtitle">The smartest way to pre-order for your team</div>
        <div style="margin-top: 1rem; font-size: 0.9rem; color: #cbd5e1; opacity: 0.8;">Made by John</div>
    </div>
    """, unsafe_allow_html=True)
    
    # 소개 섹션
    col1, col2 = st.columns([1.2, 0.8], gap="large")
    
    with col1:
        st.markdown("""
        <div class="feature-card fade-in">
            <div class="feature-icon">🚀</div>
            <h3 style="color: #1e293b; margin-bottom: 1rem;">잊어버리세요, 어제의 그 복잡했던 주문을</h3>
            <p style="color: #64748b; line-height: 1.6;">
                점심시간만 되면 울리는 수십 개의 메시지, 일일이 메뉴를 확인하고 받아 적던 시간들, 
                혹시라도 주문을 잘못 넣을까 걱정하던 마음. 
                이제, <strong>스미오(Smio)</strong>가 그 모든 불편함을 끝냅니다.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="feature-card fade-in">
            <div class="feature-icon">⚡</div>
            <h3 style="color: #1e293b; margin-bottom: 1rem;">실시간 주문 확인 가능</h3>
            <p style="color: #64748b; line-height: 1.6;">
                스미오는 스마트 미리 오더의 약자로 우리 팀의 소중한 시간과 에너지를 지키기 위해 탄생한 
                가장 스마트한 단체 주문 솔루션입니다. 더 이상 한 사람이 모든 부담을 짊어질 필요가 없습니다.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="feature-card fade-in" style="background: #1e293b; color: white; border-left: 4px solid #3b82f6;">
            <div class="feature-icon">✨</div>
            <h3 style="margin-bottom: 1.5rem; color: #e2e8f0;">주요 기능</h3>
            <ul style="list-style: none; padding: 0;">
                <li style="margin: 1rem 0; padding-left: 1.5rem; position: relative;">
                    <span style="position: absolute; left: 0;">🔗</span>
                    <strong style="color: #e2e8f0;">URL 하나로 주문방 개설</strong><br>
                    <small style="color: #cbd5e1;">네이버 플레이스 식당 주소를 붙여넣는 순간, 모두를 위한 주문판이 열립니다</small>
                </li>
                <li style="margin: 1rem 0; padding-left: 1.5rem; position: relative;">
                    <span style="position: absolute; left: 0;">📱</span>
                    <strong style="color: #e2e8f0;">실시간 메뉴 취합</strong><br>
                    <small style="color: #cbd5e1;">누가 무엇을 담았는지 모두가 함께 확인하며, 중복 주문이나 누락 걱정 없음</small>
                </li>
                <li style="margin: 1rem 0; padding-left: 1.5rem; position: relative;">
                    <span style="position: absolute; left: 0;">💰</span>
                    <strong style="color: #e2e8f0;">완벽한 자동 정산</strong><br>
                    <small style="color: #cbd5e1;">메뉴별, 사람별 최종 주문서와 총액이 자동으로 계산되어 정산이 투명하고 간편</small>
                </li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    # URL 입력 섹션
    st.markdown("""
    <div style="text-align: center; margin: 3rem 0 2rem 0;">
        <h2 style="color: #1e293b; margin-bottom: 1rem;">🎯 링크 하나로 모두의 메뉴를 투명하게 취합하세요!</h2>
        <p style="color: #64748b; font-size: 1.1rem;">네이버 플레이스 URL을 입력하고 터치 한 번으로 완벽한 주문서를 완성해보세요</p>
    </div>
    """, unsafe_allow_html=True)
    
    # URL 입력 폼
    with st.container():
        url_input = st.text_input(
            "네이버 플레이스 URL을 입력하세요", 
            placeholder="예: https://naver.me/FMAxDFTM 또는 https://map.naver.com/p/...",
            label_visibility="collapsed",
            key="url_input"
        )
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🚀 주문방 만들기", type="primary", use_container_width=True):
                if not url_input:
                    st.warning("⚠️ URL을 입력해주세요.")
                else:
                    with st.spinner("🔍 가게 정보를 불러오는 중입니다..."):
                        try:
                            normalized_url = normalize_naver_place_url(url_input)
                            if not normalized_url:
                                st.session_state.error_message = "올바른 네이버 플레이스 URL 형식이 아닙니다."
                                st.error(st.session_state.error_message)
                            else:
                                restaurant_data = scrape_restaurant_info(normalized_url)
                                
                                if restaurant_data and restaurant_data.get("menu"):
                                    st.session_state.restaurant_info = restaurant_data
                                    st.session_state.url_processed = True
                                    st.session_state.orders = []
                                    st.session_state.error_message = None
                                    st.success("✅ 주문방이 성공적으로 생성되었습니다!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.session_state.error_message = "메뉴 정보를 가져오는 데 실패했습니다. URL을 확인하시거나 다른 가게를 시도해주세요."
                                    st.error(st.session_state.error_message)
                                    
                        except Exception as e:
                            print(f"예상치 못한 오류: {e}")
                            st.session_state.error_message = "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
                            st.error(st.session_state.error_message)

# --- 페이지 2: 주문 및 현황 페이지 (URL 입력 후) ---
if st.session_state.url_processed:
    info = st.session_state.restaurant_info
    
    # 레스토랑 정보 헤더
    st.markdown(f"""
    <div class="restaurant-info fade-in">
        <div class="restaurant-name">🍽️ {info.get('name', '가게 이름 정보 없음')}</div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem;">
            <div class="restaurant-detail">
                <span style="margin-right: 0.5rem;">📍</span>
                <div>
                    <strong>주소</strong><br>
                    <small>{info.get('address', '정보 없음')}</small>
                </div>
            </div>
            <div class="restaurant-detail">
                <span style="margin-right: 0.5rem;">📞</span>
                <div>
                    <strong>전화번호</strong><br>
                    <small>{info.get('phone', '정보 없음')}</small>
                </div>
            </div>
            <div class="restaurant-detail">
                <span style="margin-right: 0.5rem;">🚗</span>
                <div>
                    <strong>주차정보</strong><br>
                    <small>{info.get('parking', '정보 없음')}</small>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 메인 주문 섹션 (모바일 최적화)
    # 모바일에서는 세로 배치, 데스크톱에서는 가로 배치
    is_mobile = st.checkbox("📱 모바일 모드", value=True, help="모바일에서 더 편한 세로 배치로 전환")
    
    if is_mobile:
        # 모바일: 세로 배치
        st.markdown("""
        <div class="order-card fade-in">
            <h3 style="margin-bottom: 1.5rem;">✍️ 메뉴 담기</h3>
        </div>
        """, unsafe_allow_html=True)
        
        if not info.get("menu") or info["menu"][0]["name"] in ["메뉴 정보를 가져올 수 없습니다", "메뉴를 수동으로 입력해주세요"]:
            st.warning("⚠️ 메뉴 정보를 자동으로 가져올 수 없습니다.")
            
            # 수동 메뉴 입력 옵션
            with st.expander("📝 메뉴를 수동으로 입력하세요", expanded=True):
                st.info("네이버 플레이스에서 메뉴를 확인하고 직접 입력해주세요.")
                
                # 메뉴 추가 폼
                with st.form("manual_menu_form"):
                    menu_name = st.text_input("🍽️ 메뉴 이름", key="manual_menu_name")
                    menu_price = st.number_input("💰 가격 (원)", min_value=0, key="manual_menu_price")
                    
                    if st.form_submit_button("➕ 메뉴 추가", use_container_width=True):
                        if menu_name.strip():
                            if "menu" not in st.session_state:
                                st.session_state.menu = []
                            st.session_state.menu.append({
                                "name": menu_name.strip(),
                                "price": menu_price if menu_price > 0 else None
                            })
                            st.success(f"✅ {menu_name.strip()} 메뉴가 추가되었습니다!")
                            st.rerun()
                
                # 추가된 메뉴 목록
                if hasattr(st.session_state, 'menu') and st.session_state.menu:
                    st.write("**📋 추가된 메뉴:**")
                    for i, menu in enumerate(st.session_state.menu):
                        price_str = f"{menu['price']:,}원" if menu.get('price') else "가격 정보 없음"
                        st.write(f"• {menu['name']} - {price_str}")
                    
                    if st.button("✅ 메뉴 입력 완료", use_container_width=True):
                        # 수동 입력된 메뉴로 restaurant_info 업데이트
                        info["menu"] = st.session_state.menu
                        st.success("✅ 메뉴 입력이 완료되었습니다!")
                        st.rerun()
        else:
            with st.form("order_form", clear_on_submit=True):
                menu_names = []
                for item in info["menu"]:
                    price_str = f"{item['price']:,}원" if item.get('price') is not None else "가격 정보 없음"
                    menu_names.append(f"{item['name']} ({price_str})")
                
                participant_name = st.text_input("👤 주문자 이름", key="participant_name_input", placeholder="예: 김철수")
                selected_menu_str = st.selectbox("🍽️ 메뉴 선택", menu_names, index=0)
                quantity = st.number_input("📊 수량", min_value=1, value=1, step=1)
                
                if selected_menu_str in menu_names:
                    selected_index = menu_names.index(selected_menu_str)
                    selected_menu_info = info["menu"][selected_index]
                    selected_menu_name = selected_menu_info["name"]
                    
                    beverage_options = None
                    special_request = None
                    if is_beverage(selected_menu_name):
                        beverage_options = st.selectbox("🧊 음료 옵션", ["(선택 안함)", "Hot", "Ice"], key="beverage_options")
                        special_request = st.text_input("📝 특별 요청사항", placeholder="예: 샷 추가, 시럽 1번만", key="special_request")
                    
                    submitted = st.form_submit_button("🛒 주문 추가하기", type="primary", use_container_width=True)

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
                                "beverage_option": beverage_options if beverage_options and beverage_options != "(선택 안함)" else None,
                                "special_request": special_request.strip() if special_request else None
                            }
                            st.session_state.orders.append(order_info)
                            st.success(f"✅ {participant_name.strip()}님의 주문이 추가되었습니다!")
                            time.sleep(1)
                            st.rerun()
        
        # 주문 현황 (모바일 버전)
        st.markdown("---")
        st.markdown("""
        <div class="status-card fade-in">
            <h3 style="margin-bottom: 1.5rem;">📊 실시간 주문 현황</h3>
        </div>
        """, unsafe_allow_html=True)
        
        if not st.session_state.orders:
            st.markdown("""
            <div style="text-align: center; padding: 2rem; background: white; border-radius: 12px; margin: 1rem 0; border: 1px solid #e2e8f0;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">🛒</div>
                <h4 style="color: #64748b;">아직 주문이 없습니다</h4>
                <p style="color: #94a3b8;">위에서 메뉴를 담아주세요!</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            orders_df = pd.DataFrame(st.session_state.orders)
            total_price = orders_df['price'].sum()
            
            # 총액 표시
            st.markdown(f"""
            <div class="metric-card fade-in pulse">
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
                
                details_text = f" `{' / '.join(details)}`" if details else ""
                
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
    
    else:
        # 데스크톱: 가로 배치 (기존 방식)
        col1, col2 = st.columns([0.6, 0.4], gap="large")
        
        with col1:
            st.markdown("""
            <div class="order-card fade-in">
                <h3 style="margin-bottom: 1.5rem;">✍️ 메뉴 담기</h3>
            </div>
            """, unsafe_allow_html=True)
            
            if not info.get("menu") or info["menu"][0]["name"] in ["메뉴 정보를 가져올 수 없습니다", "메뉴를 수동으로 입력해주세요"]:
                st.warning("⚠️ 메뉴 정보를 자동으로 가져올 수 없습니다.")
                
                # 수동 메뉴 입력 옵션
                with st.expander("📝 메뉴를 수동으로 입력하세요", expanded=True):
                    st.info("네이버 플레이스에서 메뉴를 확인하고 직접 입력해주세요.")
                    
                    # 메뉴 추가 폼
                    with st.form("manual_menu_form_desktop"):
                        menu_name = st.text_input("🍽️ 메뉴 이름", key="manual_menu_name_desktop")
                        menu_price = st.number_input("💰 가격 (원)", min_value=0, key="manual_menu_price_desktop")
                        
                        if st.form_submit_button("➕ 메뉴 추가"):
                            if menu_name.strip():
                                if "menu" not in st.session_state:
                                    st.session_state.menu = []
                                st.session_state.menu.append({
                                    "name": menu_name.strip(),
                                    "price": menu_price if menu_price > 0 else None
                                })
                                st.success(f"✅ {menu_name.strip()} 메뉴가 추가되었습니다!")
                                st.rerun()
                    
                    # 추가된 메뉴 목록
                    if hasattr(st.session_state, 'menu') and st.session_state.menu:
                        st.write("**📋 추가된 메뉴:**")
                        for i, menu in enumerate(st.session_state.menu):
                            price_str = f"{menu['price']:,}원" if menu.get('price') else "가격 정보 없음"
                            st.write(f"• {menu['name']} - {price_str}")
                        
                        if st.button("✅ 메뉴 입력 완료", key="complete_menu_desktop"):
                            # 수동 입력된 메뉴로 restaurant_info 업데이트
                            info["menu"] = st.session_state.menu
                            st.success("✅ 메뉴 입력이 완료되었습니다!")
                            st.rerun()
            else:
                with st.form("order_form_desktop", clear_on_submit=True):
                    menu_names = []
                    for item in info["menu"]:
                        price_str = f"{item['price']:,}원" if item.get('price') is not None else "가격 정보 없음"
                        menu_names.append(f"{item['name']} ({price_str})")
                    
                    participant_name = st.text_input("👤 주문자 이름", key="participant_name_input_desktop")
                    selected_menu_str = st.selectbox("🍽️ 메뉴 선택", menu_names, key="menu_select_desktop")
                    quantity = st.number_input("📊 수량", min_value=1, value=1, key="quantity_desktop")
                    
                    if selected_menu_str in menu_names:
                        selected_index = menu_names.index(selected_menu_str)
                        selected_menu_info = info["menu"][selected_index]
                        selected_menu_name = selected_menu_info["name"]
                        
                        beverage_options = None
                        special_request = None
                        if is_beverage(selected_menu_name):
                            beverage_options = st.selectbox("🧊 음료 옵션", ["(선택)", "Hot", "Ice"], key="beverage_options_desktop")
                            special_request = st.text_input("📝 특별 요청사항", placeholder="예: 샷 추가, 시럽 1번만", key="special_request_desktop")
                        
                        submitted = st.form_submit_button("🛒 주문 추가하기", type="primary", use_container_width=True)

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
            <div class="status-card fade-in">
                <h3 style="margin-bottom: 1.5rem;">📊 실시간 주문 현황</h3>
            </div>
            """, unsafe_allow_html=True)
            
            if not st.session_state.orders:
                st.markdown("""
                <div style="text-align: center; padding: 2rem; background: white; border-radius: 12px; margin: 1rem 0; border: 1px solid #e2e8f0;">
                    <div style="font-size: 4rem; margin-bottom: 1rem;">🛒</div>
                    <h4 style="color: #64748b;">아직 주문이 없습니다</h4>
                    <p style="color: #94a3b8;">왼쪽에서 메뉴를 담아주세요!</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                orders_df = pd.DataFrame(st.session_state.orders)
                total_price = orders_df['price'].sum()
                
                # 총액 표시
                st.markdown(f"""
                <div class="metric-card fade-in">
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
                    
                    details_text = f" `{' / '.join(details)}`" if details else ""
                    
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
                            placeholder="삭제할 주문 선택",
                            key="delete_order_desktop"
                        )
                        
                        if st.button("🗑️ 선택한 주문 삭제", use_container_width=True, key="delete_btn_desktop"):
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
            
            # 스타일링된 데이터프레임
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
                        
                        details_text = f" `{' / '.join(details)}`" if details else ""
                        
                        st.markdown(f"""
                        <div style="margin-left: 2rem; color: #64748b; margin-bottom: 0.5rem;">
                            • {p_order['menu']}: {p_order['quantity']}개 ({p_order['price']:,}원){details_text}
                        </div>
                        """, unsafe_allow_html=True)
            
            # 최종 합계
            grand_total = orders_df['price'].sum()
            st.markdown(f"""
            <div class="final-order" style="text-align: center; margin-top: 2rem; background: #059669;">
                <h2 style="margin: 0; color: white;">💰 총 합계: {grand_total:,}원</h2>
            </div>
            """, unsafe_allow_html=True)
    
    # 새로운 주문방 만들기 (모바일 최적화)
    st.markdown("---")
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 모바일에서는 전체 너비 버튼, 데스크톱에서는 중앙 정렬
    if st.button("🔄 새로운 주문방 만들기", use_container_width=True, key="new_order_room", 
                help="다른 식당으로 주문방을 새로 만들고 싶을 때 클릭하세요"):
        # 확인 메시지
        if st.session_state.orders:
            st.warning("⚠️ 현재 주문 내역이 모두 삭제됩니다. 정말 새로운 주문방을 만드시겠습니까?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ 네, 새로 만들기", type="primary", use_container_width=True):
                    st.session_state.url_processed = False
                    st.session_state.restaurant_info = None
                    st.session_state.orders = []
                    if hasattr(st.session_state, 'menu'):
                        delattr(st.session_state, 'menu')
                    st.success("✅ 새로운 주문방을 만들 준비가 되었습니다!")
                    st.rerun()
            with col2:
                if st.button("❌ 취소", use_container_width=True):
                    st.info("취소되었습니다.")
        else:
            st.session_state.url_processed = False
            st.session_state.restaurant_info = None
            st.session_state.orders = []
            if hasattr(st.session_state, 'menu'):
                delattr(st.session_state, 'menu')
            st.rerun()

# 모바일 최적화를 위한 추가 JavaScript
st.markdown("""
<script>
// 모바일에서 붙여넣기 지원 강화
document.addEventListener('DOMContentLoaded', function() {
    // 모든 텍스트 입력 요소에 붙여넣기 이벤트 리스너 추가
    const textInputs = document.querySelectorAll('input[type="text"], textarea');
    
    textInputs.forEach(function(input) {
        // 포커스 시 전체 선택 (모바일에서 편의성 향상)
        input.addEventListener('focus', function() {
            setTimeout(() => {
                this.select();
            }, 100);
        });
        
        // 붙여넣기 이벤트 처리
        input.addEventListener('paste', function(e) {
            setTimeout(() => {
                // Streamlit 상태 업데이트 트리거
                const event = new Event('input', { bubbles: true });
                this.dispatchEvent(event);
            }, 10);
        });
        
        // 터치 이벤트 최적화
        input.addEventListener('touchstart', function(e) {
            this.style.fontSize = '16px'; // iOS 줌 방지
        });
    });
    
    // 모바일에서 버튼 터치 피드백 강화
    const buttons = document.querySelectorAll('button');
    buttons.forEach(function(button) {
        button.addEventListener('touchstart', function() {
            this.style.transform = 'scale(0.95)';
        });
        
        button.addEventListener('touchend', function() {
            this.style.transform = 'scale(1)';
        });
    });
});

// 뷰포트 메타태그 동적 추가 (모바일 최적화)
if (!document.querySelector('meta[name="viewport"]')) {
    const viewport = document.createElement('meta');
    viewport.name = 'viewport';
    viewport.content = 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no';
    document.head.appendChild(viewport);
}
</script>
""", unsafe_allow_html=True)