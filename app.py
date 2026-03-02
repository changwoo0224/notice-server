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

# === 플라스크 서버 설정 ===
app = Flask(__name__)

# === 보안 무시 어댑터 ===
class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        context = ssl_.create_urllib3_context(ciphers='DEFAULT@SECLEVEL=1')
        context.check_hostname = False 
        context.verify_mode = ssl.CERT_NONE
        self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize, block=block, ssl_context=context)

# === 핵심 크롤링 로직 (함수로 분리) ===
def get_notices(url):
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url
    
    result_list = [] # 결과를 담을 리스트
    
    try:
        session = requests.Session()
        session.mount('https://', LegacySSLAdapter()) 
        headers = {'User-Agent': 'Mozilla/5.0'}
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 1차 접속
        response = session.get(url, headers=headers, timeout=10, verify=False)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        # 리다이렉트(이동) 체크
        meta_refresh = soup.find('meta', attrs={'http-equiv': re.compile(r'refresh', re.I)})
        if meta_refresh:
            content = meta_refresh.get('content', '')
            if 'url=' in content:
                new_path = content.split('url=')[-1].strip()
                url = urljoin(url, new_path) # URL 업데이트
                # 2차 접속
                response = session.get(url, headers=headers, timeout=10, verify=False)
                response.encoding = 'utf-8'
                soup = BeautifulSoup(response.text, 'html.parser')

        # 링크 찾기
        links = soup.find_all('a')
        keywords = ['공지', 'JBNU소식', '학사공지', '일반공지', '장학', 'Notice', 'news', 'News', '게시판'] 
        found_urls = set() # 중복 방지용

        for link in links:
            text = link.get_text().strip()
            href = link.get('href')
            
            if not href or not text: continue
            if 'javascript' in href or '#' == href: continue

            for key in keywords:
                if key in text:
                    full_url = urljoin(url, href)
                    if full_url not in found_urls:
                        # 아이폰에게 보낼 깔끔한 데이터 형식 (JSON)
                        result_list.append({
                            "title": text,
                            "link": full_url
                        })
                        found_urls.add(full_url)
                    break 
        
        return {"status": "success", "data": result_list[:10]} # 최대 10개

    except Exception as e:
        return {"status": "error", "message": str(e)}

# === 🌐 웹 서버 접속 경로 설정 ===
# 아이폰이 '주소/search?url=학교주소' 로 접속하면 이 함수가 실행됨
@app.route('/search', methods=['GET'])
def search_api():
    target_url = request.args.get('url') # 아이폰이 보낸 URL 받기
    if not target_url:
        return jsonify({"status": "error", "message": "URL을 입력해주세요."})
    
    # 크롤링 실행!
    result = get_notices(target_url)
    return jsonify(result) # 결과를 JSON으로 변환해서 발사

# === 서버 실행 ===
if __name__ == "__main__":
    # 내 컴퓨터(0.0.0.0)의 5001번 포트에서 서버를 켭니다.
    app.run(host='0.0.0.0', port=5001, debug=True)
