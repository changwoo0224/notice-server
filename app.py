import os
from flask import Flask, request, jsonify
import requests
import ssl
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util import ssl_
import urllib3
from urllib.parse import urlparse, parse_qs, urljoin
import time

app = Flask(__name__)

# === 1. 보안 설정 (SSL 무시) ===
class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        context = ssl_.create_urllib3_context(ciphers='DEFAULT@SECLEVEL=1')
        context.check_hostname = False 
        context.verify_mode = ssl.CERT_NONE
        self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize, block=block, ssl_context=context)

def get_request(method, url, params=None, data=None):
    try:
        session = requests.Session()
        session.mount('https://', LegacySSLAdapter())
        headers = {'User-Agent': 'Mozilla/5.0'}
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        if method == 'GET':
            response = session.get(url, headers=headers, params=params, timeout=10, verify=False)
        else:
            response = session.post(url, headers=headers, data=data, timeout=10, verify=False)
            
        response.encoding = 'utf-8' 
        return BeautifulSoup(response.text, 'html.parser'), response.url
    except:
        return None, ""

# === 2. V21: 도메인 인지형 스마트 엔진 ===
def search_hybrid_v21(target_url, keyword):
    if not target_url.startswith("http"): target_url = "https://" + target_url
    
    # 기본 접속 및 데이터 수집
    soup_init, real_url = get_request('GET', target_url)
    if not soup_init: return []

    base_payload = {}
    parsed = urlparse(real_url)
    
    # Hidden 값 수집 (보안 및 게시판 ID 유지용)
    inputs = soup_init.find_all('input', {'type': 'hidden'})
    for inp in inputs:
        name, value = inp.get('name'), inp.get('value')
        if name and value: base_payload[name] = value

    # [케이스 1] 전북대 및 국립대 계열
    if "jbnu.ac.kr" in real_url or "ac.kr" in real_url:
        if "jbnu.ac.kr" in real_url and "menu" not in base_payload:
            if "sub01.do" in real_url: base_payload['menu'] = '2377'
            elif "sub02.do" in real_url: base_payload['menu'] = '2397'
        
        base_payload.update({'searchKeyword': keyword, 'searchCondition': '0'})
        return try_search('GET', real_url.split('?')[0], base_payload, keyword)

    # [케이스 2] 교육청 및 학교 계열 (POST 방식 우선)
    elif "hs.kr" in real_url or "sen.go.kr" in real_url:
        base_payload.update({'searchWrd': keyword, 'searchCondition': '0'})
        res = try_search('POST', real_url.split('?')[0], base_payload, keyword)
        if res: return res
        base_payload['srchWrd'] = keyword
        return try_search('POST', real_url.split('?')[0], base_payload, keyword)

    # [케이스 3] 일반/글로벌 사이트
    else:
        strategies = [('GET', 'q'), ('GET', 'query'), ('GET', 's'), ('POST', 'searchKeyword')]
        for method, param in strategies:
            payload = base_payload.copy()
            payload[param] = keyword
            res = try_search(method, real_url.split('?')[0], payload, keyword)
            if res: return res
            time.sleep(0.3)

    return []

def try_search(method, url, payload, keyword):
    soup, final_url = get_request(method, url, params=payload if method=='GET' else None, data=payload if method=='POST' else None)
    if not soup: return []
    
    results = []
    seen = set()
    for link in soup.find_all('a'):
        text, href = link.get_text().strip(), link.get('href')
        if not text or not href or 'javascript' in href or '#' in href: continue
        if keyword.replace(" ", "") in text.replace(" ", ""):
            full_url = urljoin(final_url, href)
            if full_url not in seen:
                results.append({"title": text, "link": full_url})
                seen.add(full_url)
    return results

@app.route('/search', methods=['GET'])
def search_api():
    t_url, kw = request.args.get('url'), request.args.get('keyword')
    if not t_url or not kw: return jsonify({"status": "error", "message": "필수값 누락"})
    return jsonify({"status": "success", "data": search_hybrid_v21(t_url, kw)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)