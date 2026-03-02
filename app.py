from flask import Flask, request, jsonify
import requests
import ssl
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util import ssl_
import urllib3

app = Flask(__name__)

# === 보안 무시 어댑터 (기존과 동일) ===
class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        context = ssl_.create_urllib3_context(ciphers='DEFAULT@SECLEVEL=1')
        context.check_hostname = False 
        context.verify_mode = ssl.CERT_NONE
        self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize, block=block, ssl_context=context)

# === ⭐️ [수정됨] 키워드를 받아서 처리하는 함수 ===
def get_notices(url, user_keyword):
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    
    result_list = []
    
    try:
        session = requests.Session()
        session.mount('https://', LegacySSLAdapter()) 
        headers = {'User-Agent': 'Mozilla/5.0'}
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 1차 접속
        response = session.get(url, headers=headers, timeout=10, verify=False)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        # 리다이렉트 체크
        meta_refresh = soup.find('meta', attrs={'http-equiv': re.compile(r'refresh', re.I)})
        if meta_refresh:
            content = meta_refresh.get('content', '')
            if 'url=' in content:
                new_path = content.split('url=')[-1].strip()
                url = urljoin(url, new_path)
                response = session.get(url, headers=headers, timeout=10, verify=False)
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.text, 'html.parser')

        # 링크 찾기
        links = soup.find_all('a')
        
        # ⭐️ [핵심] 사용자가 키워드를 줬으면 그것만 쓰고, 없으면 기본값 사용
        if user_keyword:
            keywords = [user_keyword] # 사용자가 입력한 단어 하나만 타겟팅
        else:
            keywords = ['공지', 'Notice', 'news', '게시판'] # 기본값

        found_urls = set()

        for link in links:
            text = link.get_text().strip()
            href = link.get('href')
            
            if not href or not text: continue
            if 'javascript' in href or '#' == href: continue

            # 키워드 검사
            for key in keywords:
                if key in text: # 대소문자 구분을 없애려면 .lower() 사용 가능
                    full_url = urljoin(url, href)
                    if full_url not in found_urls:
                        result_list.append({
                            "title": text,
                            "link": full_url
                        })
                        found_urls.add(full_url)
                    break 
        
        return {"status": "success", "data": result_list[:15]} # 15개 정도 가져오기

    except Exception as e:
        return {"status": "error", "message": str(e)}

# === API 경로 설정 ===
@app.route('/search', methods=['GET'])
def search_api():
    target_url = request.args.get('url')
    keyword = request.args.get('keyword') # ⭐️ URL에서 키워드 꺼내기
    
    if not target_url:
        return jsonify({"status": "error", "message": "URL을 입력해주세요."})
    
    # 크롤링 실행 (키워드 전달)
    result = get_notices(target_url, keyword)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001, debug=True)