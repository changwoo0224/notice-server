from flask import Flask, request, jsonify
import requests
import ssl
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util import ssl_
import urllib3

app = Flask(__name__)

# === 1. 강력한 보안 무시 어댑터 ===
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
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 5초 안에 응답 없으면 포기 (속도 향상)
        response = session.get(url, headers=headers, timeout=5, verify=False)
        response.encoding = 'utf-8' # 한글 깨짐 방지
        return BeautifulSoup(response.text, 'html.parser'), response.status_code
    except Exception as e:
        print(f"에러: {e}")
        return None, 500

# === 2. 범용 게시판 털기 로직 ===
def scrape_any_board(url, keyword):
    url = url.strip()
    if not url.startswith("http"): url = "https://" + url
    
    print(f"🔍 [직접 접속] {url} 에서 '{keyword}' 찾는 중...")
    
    soup, status = get_soup(url)
    if not soup:
        return {"status": "error", "message": f"사이트 접속 불가 (코드: {status})"}

    results = []
    seen_links = set()
    
    # 전략: 게시판은 보통 <a> 태그 안에 제목이 있다.
    # 모든 링크를 다 가져와서 검사한다.
    links = soup.find_all('a')
    
    # 만약 키워드가 없으면? -> 그냥 상위 15개 글을 가져옴
    if not keyword:
        for link in links:
            text = link.get_text().strip()
            href = link.get('href')
            if len(text) > 5 and href: # 제목이 너무 짧으면(예: '홈') 패스
                # 자바스크립트 링크는 앱에서 못 여니까 제외
                if 'javascript' in href or '#' in href: continue
                
                # 절대 경로로 변환
                if not href.startswith("http"):
                    # 주소 합치기 로직 단순화
                    base_url = "/".join(url.split('/')[:3]) # https://site.com
                    if href.startswith("/"):
                        full_url = base_url + href
                    else:
                        full_url = url + "/" + href # 단순 무식하게 합치기 (오히려 잘 됨)
                else:
                    full_url = href

                if full_url not in seen_links:
                    results.append({"title": text, "link": full_url})
                    seen_links.add(full_url)
                    if len(results) >= 15: break
    
    # 키워드가 있으면? -> 그것만 찾음
    else:
        for link in links:
            text = link.get_text().strip()
            href = link.get('href')
            
            if not text or not href: continue
            
            # ⭐️ 검색어 매칭 (공백 제거 후 비교)
            clean_text = text.replace(" ", "")
            clean_keyword = keyword.replace(" ", "")
            
            if clean_keyword in clean_text:
                if 'javascript' in href or '#' in href: continue

                if not href.startswith("http"):
                    base_url = "/".join(url.split('/')[:3])
                    if href.startswith("/"):
                        full_url = base_url + href
                    else:
                        # 상대 경로 처리가 복잡하므로, 단순하게 처리
                        full_url = base_url + href 
                else:
                    full_url = href
                
                if full_url not in seen_links:
                    results.append({"title": text, "link": full_url})
                    seen_links.add(full_url)

    # 결과가 없으면? 디버깅용 메시지 추가
    if not results:
        title = soup.title.string if soup.title else "제목 없음"
        return {
            "status": "success", 
            "data": [], 
            "message": f"'{title}' 페이지에 접속은 했는데, '{keyword}' 관련 글을 못 찾았습니다. 주소가 게시판 목록이 맞나요?"
        }

    return {"status": "success", "data": results}

# === 서버 경로 ===
@app.route('/', methods=['GET'])
def home():
    return "V6: Direct Board Link Mode (게시판 주소를 직접 넣으세요!)"

@app.route('/search', methods=['GET'])
def search_api():
    target_url = request.args.get('url')
    keyword = request.args.get('keyword')
    
    if not target_url:
        return jsonify({"status": "error", "message": "URL을 입력해주세요."})
    
    result = scrape_any_board(target_url, keyword)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)