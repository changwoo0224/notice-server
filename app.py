from flask import Flask, request, jsonify
import requests
import ssl
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util import ssl_
import urllib3

app = Flask(__name__)

# === 보안 설정 ===
class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        context = ssl_.create_urllib3_context(ciphers='DEFAULT@SECLEVEL=1')
        context.check_hostname = False 
        context.verify_mode = ssl.CERT_NONE
        self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize, block=block, ssl_context=context)

def get_soup(url):
    try:
        session = requests.Session()
        session.mount('https://', LegacySSLAdapter())
        headers = {'User-Agent': 'Mozilla/5.0'}
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # ⭐️ [핵심 수정] 타임아웃을 3초로 줄임 (빨리빨리 넘어가기 위해)
        response = session.get(url, headers=headers, timeout=3, verify=False)
        response.encoding = 'utf-8' 
        return BeautifulSoup(response.text, 'html.parser')
    except:
        return None

# === V12: 고속 검색 모드 (Fast Search) ===
def smart_search_fast(base_url, keyword):
    base_url = base_url.strip()
    if not base_url.startswith("http"): base_url = "https://" + base_url
    
    print(f"🚀 [V12 고속 검색] '{keyword}' 검색 시작")
    
    # 순서 중요: 전북대는 searchKeyword를 쓰므로 맨 앞에 배치
    search_params = ["searchKeyword", "q", "query", "s", "srSearchVal"]
    
    all_results = []
    seen_links = set()
    connector = "&" if "?" in base_url else "?"
    
    for param in search_params:
        target_url = f"{base_url}{connector}{param}={keyword}"
        if param == "searchKeyword": target_url += "&searchCondition=0"

        # print(f"👉 시도: {param}") # 로그 줄임
        
        soup = get_soup(target_url)
        if not soup: continue # 3초 안에 답 없으면 바로 다음으로!
        
        links = soup.find_all('a')
        found_count = 0
        
        for link in links:
            text = link.get_text().strip()
            href = link.get('href')
            if not text or not href: continue
            if 'javascript' in href or '#' in href: continue
            
            clean_text = text.replace(" ", "")
            clean_keyword = keyword.replace(" ", "") if keyword else ""
            
            if clean_keyword in clean_text:
                if not href.startswith("http"):
                    if href.startswith("/"):
                        domain = "/".join(base_url.split('/')[:3])
                        full_url = domain + href
                    else:
                        url_path = base_url.split('?')[0]
                        parent_path = "/".join(url_path.split('/')[:-1])
                        full_url = parent_path + "/" + href
                else:
                    full_url = href
                
                if full_url not in seen_links:
                    all_results.append({"title": text, "link": full_url})
                    seen_links.add(full_url)
                    found_count += 1
        
        # 하나라도 찾으면 즉시 종료 (속도 최우선)
        if found_count > 0:
            print(f"   ✅ '{param}'에서 {found_count}개 발견! 탐색 종료.")
            break
            
    return all_results

@app.route('/', methods=['GET'])
def home():
    return "V12: High-Speed Search Mode (타임아웃 단축)"

@app.route('/search', methods=['GET'])
def search_api():
    target_url = request.args.get('url')
    keyword = request.args.get('keyword')
    if not target_url: return jsonify({"status": "error", "message": "URL 필요"})
    
    # 키워드 없으면 그냥 긁어오기
    if not keyword:
         # (단순 긁어오기 로직은 V7과 동일하다고 가정, 여기선 생략하고 빈 리스트 리턴하거나 기존 scrape_any_board 사용)
         # 편의상 검색 로직만 호출합니다. 키워드 없으면 0개 리턴됨.
         return jsonify({"status": "success", "data": [], "message": "키워드를 입력해주세요."})

    results = smart_search_fast(target_url, keyword)
    
    if not results:
        return jsonify({"status": "success", "data": [], "message": "검색 결과 0건"})
        
    return jsonify({"status": "success", "data": results})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)