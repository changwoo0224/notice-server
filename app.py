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
        response = session.get(url, headers=headers, timeout=8, verify=False)
        response.encoding = 'utf-8' 
        return BeautifulSoup(response.text, 'html.parser')
    except:
        return None

# === 🌐 V10: 월드 와이드 스마트 검색 ===
def smart_search(base_url, keyword):
    base_url = base_url.strip()
    if not base_url.startswith("http"): base_url = "https://" + base_url
    
    # ? 뒷부분 제거 (순수 URL만 남김)
    clean_url = base_url.split('?')[0]
    
    print(f"🚀 [V10 글로벌 검색] '{keyword}' 탐색 시작...")
    
    # ⭐️ 전 세계 웹사이트 검색 변수 TOP 7
    # 이 리스트에 있는 걸 순서대로 다 찔러봅니다.
    search_params = [
        "searchKeyword", # 한국 공공기관/대학 표준 (1순위)
        "q",             # 구글, 글로벌 표준 (2순위)
        "s",             # 워드프레스(WordPress) 전 세계 40% 점유 (3순위)
        "query",         # 네이버, 다음, 많은 포털형 사이트
        "kwd",           # Keyword 약자 (한국 사이트 자주 씀)
        "keyword",       # 정직한 변수명
        "srSearchVal"    # 옛날 게시판 솔루션
    ]
    
    all_results = []
    seen_links = set()
    
    for param in search_params:
        target_url = f"{clean_url}?{param}={keyword}"
        # print(f"   👉 찌르는 중: ?{param}=") # 로그 너무 많으면 주석 처리
        
        soup = get_soup(target_url)
        if not soup: continue
        
        links = soup.find_all('a')
        found_count = 0
        
        for link in links:
            text = link.get_text().strip()
            href = link.get('href')
            
            if not text or not href: continue
            if 'javascript' in href or '#' in href: continue
            
            clean_text = text.replace(" ", "")
            clean_keyword = keyword.replace(" ", "")
            
            # 검색 결과에서 키워드 발견!
            if clean_keyword in clean_text:
                if not href.startswith("http"):
                    base_root = "/".join(base_url.split('/')[:3])
                    if href.startswith("/"):
                        full_url = base_root + href
                    else:
                        full_url = "/".join(clean_url.split('/')[:-1]) + "/" + href
                else:
                    full_url = href
                
                if full_url not in seen_links:
                    all_results.append({"title": text, "link": full_url})
                    seen_links.add(full_url)
                    found_count += 1
        
        # 하나라도 찾았으면 그 변수가 정답이므로 반복문 종료! (시간 절약)
        if found_count > 0:
            print(f"   ✅ 성공! 정답 변수는 '?{param}=' 였습니다. ({found_count}개 발견)")
            break
            
    return all_results

# === 서버 경로 ===
@app.route('/', methods=['GET'])
def home():
    return "V10: World-Wide Search Mode (글로벌 호환성 패치)"

@app.route('/search', methods=['GET'])
def search_api():
    target_url = request.args.get('url')
    keyword = request.args.get('keyword')
    if not target_url: return jsonify({"status": "error", "message": "URL 필요"})
    
    results = smart_search(target_url, keyword)
    
    if not results:
        return jsonify({"status": "success", "data": [], "message": "모든 검색 방법을 시도했으나 실패했습니다."})
        
    return jsonify({"status": "success", "data": results})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)