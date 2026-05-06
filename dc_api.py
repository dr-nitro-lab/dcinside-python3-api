import asyncio
import json
import lxml.html
from datetime import datetime, timedelta
import itertools
import aiohttp
import filetype
from urllib.parse import urljoin

DOCS_PER_PAGE = 200

GET_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 7.0; SM-G892A Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/67.0.3396.87 Mobile Safari/537.36"
     }
XML_HTTP_REQ_HEADERS = {
    "Accept": "*/*",
    "Connection": "keep-alive",
    "User-Agent": "Mozilla/5.0 (Linux; Android 7.0; SM-G892A Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/67.0.3396.87 Mobile Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.5",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

POST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Linux; Android 7.0; SM-G892A Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/67.0.3396.87 Mobile Safari/537.36",
    }

PC_GET_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }

PC_AJAX_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://gall.dcinside.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    }

PC_SERVICE_CODE_ALPHABET = "yL/M=zNa0bcPQdReSfTgUhViWjXkYIZmnpo+qArOBslCt2D3uE4Fv5G6wH178xJ9K"
PC_WRITE_MIN_WAIT_SECONDS = 3.0

GALLERY_POSTS_COOKIES = {
    "__gat_mobile_search": 1,
    "list_count": DOCS_PER_PAGE,
    }

import re
def unquote(encoded):
    return re.sub(r'\\u([a-fA-F0-9]{4}|[a-fA-F0-9]{2})', lambda m: chr(int(m.group(1), 16)), encoded)
def quote(decoded):
    arr = []
    for c in decoded:
        t = hex(ord(c))[2:].upper() 
        if len(t) >= 4:
            arr.append("%u" + t)
        else:
            arr.append("%" + t)
    return "".join(arr)
def peek(iterable):
    try:
        first = next(iterable)
    except StopIteration:
        return None
    return first, itertools.chain((first,), iterable)

class DocumentIndex:
    __slots__ = ["id", "subject", "title", "board_id", "has_image", "author", "time", "view_count", "comment_count", "voteup_count", "document", "comments", "image_available"]
    def __init__(self, id, board_id, title, has_image, author, time, view_count, comment_count, voteup_count, document, comments, subject, image_available):
        self.id = id
        self.board_id = board_id
        self.title = title
        self.has_image = has_image
        self.author = author
        self.time = time
        self.view_count = view_count
        self.comment_count = comment_count
        self.voteup_count = voteup_count
        self.document = document
        self.comments = comments
        self.subject = subject
        self.image_available = image_available
    def __str__(self):
        return f"{self.subject or ''}\t|{self.id}\t|{self.time.isoformat()}\t|{self.author}\t|{self.title}({self.comment_count}) +{self.voteup_count}"

class Document:
    __slots__ = ["id", "board_id", "title", "author", "author_id", "contents", "images", "html", "view_count", "voteup_count", "votedown_count", "logined_voteup_count", "time", "subject", "comments"]
    def __init__(self, id, board_id, title, author, author_id, contents, images, html, view_count, voteup_count, votedown_count, logined_voteup_count, time, comments, subject=None):
        self.id = id
        self.board_id = board_id
        self.title = title
        self.author = author
        self.author_id = author_id
        self.contents = contents
        self.images = images
        self.html = html
        self.view_count = view_count
        self.voteup_count = voteup_count
        self.votedown_count = votedown_count
        self.logined_voteup_count = logined_voteup_count
        self.comments = comments
        self.time = time
        self.subject = None
    def __str__(self):
        return f"{self.subject or ''}\t|{self.id}\t|{self.time.isoformat()}\t|{self.author}\t|{self.title}({self.comment_count}) +{self.voteup_count} -{self.votedown_count}\n{self.contents}"

class Comment:
    __slots__ = ["id", "is_reply", "author", "author_id", "contents", "dccon", "voice", "time"]
    def __init__(self, id, is_reply, author, author_id, contents, dccon, voice, time):
        self.id = id
        self.is_reply = is_reply
        self.author = author
        self.author_id = author_id
        self.contents = contents
        self.dccon = dccon
        self.voice = voice
        self.time = time
    def __str__(self):
        return f"ㄴ{'ㄴ' if self.is_reply else ''} {self.author}: {self.contents or ''}{self.dccon or ''}{self.voice or ''} | {self.time}"

class Image:
    __slots__ = ["src", "document_id", "board_id", "session"]
    def __init__(self, src, document_id, board_id, session):
        self.src = src
        self.document_id = document_id
        self.board_id = board_id
        self.session = session
    async def load(self):
        headers = GET_HEADERS.copy()
        headers["Referer"] = "https://m.dcinside.com/board/{}/{}".format(self.board_id, self.document_id)
        async with self.session.get(self.src, cookies=GALLERY_POSTS_COOKIES, headers=headers) as res:
            return await res.read()
    async def download(self, path):
        headers = GET_HEADERS.copy()
        headers["Referer"] = "https://m.dcinside.com/board/{}/{}".format(self.board_id, self.document_id)
        async with self.session.get(self.src, cookies=GALLERY_POSTS_COOKIES, headers=headers) as res:
            bytes = await res.read()
            ext = filetype.guess(bytes).extension
            with open(path + '.' + ext, 'wb') as f:
                f.write(bytes)



class API:
    def __init__(self):
        self.session = aiohttp.ClientSession(headers=GET_HEADERS, cookies={"_ga": "GA1.2.693521455.1588839880"})
    async def close(self):
        await self.session.close()
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args, **kwargs):
        await self.close()
    async def watch(self, board_id):
        pass
    async def gallery(self, name=None):
        url = "https://m.dcinside.com/galltotal"
        gallerys={}
        async with self.session.get(url) as res:
            text = await res.text()
            parsed = lxml.html.fromstring(text)
        for i in parsed.xpath('//*[@id="total_1"]/li'):
            for e in i.iter():
                if e.tag == "a":
                    board_name = e.text
                    board_id = e.get("href").split("/")[-1]
                    if name:
                        if name in board_name:
                            gallerys[board_name] = board_id
                    else:
                        gallerys[board_name] = board_id
        return gallerys
    async def board(self, board_id, num=-1, start_page=1, recommend=False, document_id_upper_limit=None, document_id_lower_limit=None, is_minor=False):
        page = start_page
        while num:
            if recommend:
                url = "https://m.dcinside.com/board/{}?recommend=1&page={}".format(board_id, page)
            else:
                url = "https://m.dcinside.com/board/{}?page={}".format(board_id, page)
            async with self.session.get(url) as res:
                text = await res.text()
                parsed = lxml.html.fromstring(text)
            doc_headers = (i[0] for i in parsed.xpath("//ul[contains(@class, 'gall-detail-lst')]/li") if not i.get("class", "").startswith("ad"))
            for doc in doc_headers:
                document_id = doc[0].get("href").split("/")[-1].split("?")[0]
                if document_id_upper_limit and int(document_id_upper_limit) <= int(document_id): continue
                if document_id_lower_limit and int(document_id_lower_limit) >= int(document_id): return
                if len(doc[0][1]) == 5:
                    subject = doc[0][1][0].text
                    author = doc[0][1][1].text
                    time= self.__parse_time(doc[0][1][2].text)
                    view_count= int(doc[0][1][3].text.split()[-1])
                    voteup_count= int(doc[0][1][4][0].text.split()[-1])
                else:
                    subject = None
                    author = doc[0][1][0].text
                    time= self.__parse_time(doc[0][1][1].text)
                    view_count= int(doc[0][1][2].text.split()[-1])
                    voteup_count= int(doc[0][1][3].text_content().split()[-1])
                if "sp-lst-img" in doc[0][0][0].get("class"):
                    image_available = True
                else:
                    image_available = False
                title = doc[0][0][1].text
                indexdata = DocumentIndex(
                    id= document_id,
                    board_id=board_id,
                    title= title,
                    has_image= doc[0][0][0].get("class").endswith("img"),
                    author= author,
                    view_count= view_count,
                    voteup_count= voteup_count,
                    comment_count= int(doc[1][0].text),
                    document= lambda: self.document(board_id, document_id),
                    comments= lambda: self.comments(board_id, document_id),
                    time= time,
                    subject=subject,
                    image_available=image_available
                    )
                yield(indexdata)
                num-=1
                if num==0: 
                    break
            if not doc_headers: 
                break
            else: 
                page+=1
    async def document(self, board_id, document_id):
        url = "https://m.dcinside.com/board/{}/{}".format(board_id, document_id)
        async with self.session.get(url) as res:
            text = await res.text()
            parsed = lxml.html.fromstring(text)
        doc_content_container = parsed.xpath("//div[@class='thum-txtin']")
        doc_head_containers = parsed.xpath("//div[starts-with(@class, 'gallview-tit-box')]")
        if not len(doc_head_containers):
            return None
        doc_head_container = doc_head_containers[0]
        if len(doc_content_container):
            title = " ".join(doc_head_container[0].text_content().strip().split())
            ginfo = doc_head_container.xpath(".//ul[contains(@class, 'ginfo2')]/li")
            author = " ".join(ginfo[0].text_content().strip().split()).replace(" (", "(")
            gallog_links = doc_head_container.xpath(".//a[contains(@href, '/gallog/')]/@href")
            author_id = gallog_links[0].rstrip("/").split("/")[-1] if gallog_links else None
            time = ginfo[1].text_content().strip()
            doc_content = parsed.xpath("//div[@class='thum-txtin']")[0]
            for adv in doc_content.xpath("div[@class='adv-groupin']"):
                adv.getparent().remove(adv)
            for adv in doc_content.xpath("//img"):
                if adv.get("src", "").startswith("https://nstatic") and not adv.get("data-original"):
                    adv.getparent().remove(adv)
            stats = parsed.xpath("//ul[contains(@class, 'ginfo2')]")
            view_count = 0
            if len(stats) > 1:
                view_count_match = re.search(r"조회수\s*([0-9,]+)", stats[1].text_content())
                if view_count_match:
                    view_count = int(view_count_match.group(1).replace(",", ""))
            def parse_count(xpath):
                nodes = parsed.xpath(xpath)
                if not nodes:
                    # Some minor-gallery settings hide counters such as nonrecomm_btn.
                    return 0
                text = nodes[0].text_content().strip().replace(",", "")
                return int(text) if text.isdigit() else 0
            return Document(
                    id = document_id,
                    board_id = board_id,
                    title= title,
                    author= author,
                    author_id =author_id,
                    contents= '\n'.join(i.strip() for i in doc_content.itertext() if i.strip() and not i.strip().startswith("이미지 광고")),
                    images= [Image(
                        src=i.get("data-original", i.get("src")),
                        board_id=board_id,
                        document_id=document_id,
                        session=self.session)
                        for i in doc_content.xpath("//img")
                            if i.get("data-original") or (not i.get("src","").startswith("https://nstatic") and
                                not i.get("src", "").startswith("https://img.iacstatic.co.kr") and i.get("src"))],
                    html= lxml.html.tostring(doc_content, encoding=str),
                    view_count= view_count,
                    voteup_count= parse_count("//span[@id='recomm_btn']"),
                    votedown_count= parse_count("//span[@id='nonrecomm_btn']"),
                    logined_voteup_count= parse_count("//span[@id='recomm_btn_member']"),
                    comments= lambda: self.comments(board_id, document_id),
                    time= self.__parse_time(time)
                    )
        else:
            # fail due to unusual tags in mobile version
            # at now, just skip it
            return None
        ''' !TODO: use an alternative(PC) protocol to fetch document
        else:
            url = "https://gall.dcinside.com/{}?no={}".format(board_id, document_id)
            res = sess.get(url, timeout=TIMEOUT, headers=ALTERNATIVE_GET_HEADERS)
            parsed = lxml.html.fromstring(res.text)
            doc_content = parsed.xpath("//div[@class='thum-txtin']")[0]
            return '\n'.join(i.strip() for i in doc_content.itertext() if i.strip() and not i.strip().startswith("이미지 광고")), [i.get("src") for i in doc_content.xpath("//img") if not i.get("src","").startswith("https://nstatic")], comments(board_id, document_id, sess=sess)
        '''
    async def comments(self, board_id, document_id, num=-1, start_page=1):
        url = "https://m.dcinside.com/ajax/response-comment"
        for page in range(start_page, 999999):
            payload = {"id": board_id, "no": document_id, "cpage": page, "managerskill":"", "del_scope": "1", "csort": ""}
            async with self.session.post(url, headers=XML_HTTP_REQ_HEADERS, data=payload) as res:
                parsed = lxml.html.fromstring(await res.text())
            if not len(parsed[1].xpath("li")): break
            for li in parsed[1].xpath("li"):
                if not len(li[0]) or not li[0].text_content().strip(): continue
                author = " ".join(li[0].text_content().strip().split()).replace(" (", "(")
                gallog_links = li[0].xpath(".//a[contains(@href, '/gallog/')]/@href")
                author_id = gallog_links[0].rstrip("/").split("/")[-1] if gallog_links else None
                yield Comment(
                    id= li.get("no"),
                    is_reply = "comment-add" in li.get("class", "").strip().split(),
                    author = author,
                    author_id= author_id,
                    contents= '\n'.join(i.strip() for i in li[1].itertext()),
                    dccon= li[1][0].get("data-original", li[1][0].get("src", None)) if len(li[1]) and li[1][0].tag=="img" else None,
                    voice= li[1][0].get("src", None) if len(li[1]) and li[1][0].tag=="iframe" else None,
                    time= self.__parse_time(li[2].text))
                num -= 1
                if num == 0:
                    return
            page_num_els = parsed.xpath("span[@class='pgnum']")
            if page_num_els:
                p = page_num_els[0].itertext()
                next(p)
                if page == next(p)[1:]: 
                    break
            else: 
                break 
    async def write_comment(self, board_id, document_id, contents="", dccon_id="", dccon_src="", parent_comment_id="", name="", password="", is_minor=False):
        url = "https://m.dcinside.com/board/{}/{}".format(board_id, document_id)
        async with self.session.get(url) as res:
            parsed = lxml.html.fromstring(await res.text())
        hide_robot = parsed.xpath("//input[@class='hide-robot']")[0].get("name")
        csrf_token = parsed.xpath("//meta[@name='csrf-token']")[0].get("content")
        title = parsed.xpath("//span[@class='tit']")[0].text.strip()
        board_name = parsed.xpath("//a[@class='gall-tit-lnk']")[0].text.strip()
        con_key = await self.__access("com_submit", url, require_conkey=False, csrf_token=csrf_token)
        header = XML_HTTP_REQ_HEADERS.copy()
        header["Referer"] = url
        header["Host"] = "m.dcinside.com"
        header["Origin"] = "https://m.dcinside.com"
        header["X-CSRF-TOKEN"] = csrf_token
        cookies = {
            "m_dcinside_" + board_id: board_id,
            "m_dcinside_lately": quote(board_id + "|" + board_name + ","),
            "_ga": "GA1.2.693521455.1588839880",
            }
        url = "https://m.dcinside.com/ajax/comment-write"
        payload = {
                "comment_memo": contents,
                "comment_nick": name,
                "comment_pw": password,
                "mode": "com_write",
                "comment_no": parent_comment_id,
                "id": board_id,
                "no": document_id,
                "best_chk": "",
                "subject": title,
                "board_id": "0",
                "reple_id":"",
                "cpage": "1",
                "con_key": con_key,
                hide_robot: "1",
                }
        if dccon_id: payload["detail_idx"] = dccon_id
        if dccon_src: payload["comment_memo"] = "<img src='{}' class='written_dccon' alt='1'>".format(dccon_src)
        #async with self.session.post(url, headers=header, data=payload, cookies=cookies) as res:
        async with self.session.post(url, headers=header, data=payload, cookies=cookies) as res:
            parsed = await res.text()
        try:
            parsed = json.loads(parsed)
        except Exception as e:
            raise Exception("Error while writing comment: " + unquote(str(parsed)))
        if "data" not in parsed:
            raise Exception("Error while writing comment: " + unquote(str(parsed)))
        return str(parsed["data"])
    async def modify_document(self, board_id, document_id, title="", contents="", name="", password="", is_minor=False):
        if not password:
            url = "https://m.dcinside.com/write/{}/modify/{}".format(board_id, document_id)
            async with self.session.get(url) as res:
                return await self.__write_or_modify_document(board_id, title, contents, name, password, intermediate=await res.text(), intermediate_referer=url, document_id=document_id, is_minor=is_minor)
        url = "https://m.dcinside.com/confirmpw/{}/{}?mode=modify".format(board_id, document_id)
        referer = url
        async with self.session.get(url) as res:
            parsed = lxml.html.fromstring(await res.text())
        token = parsed.xpath("//input[@name='_token']")[0].get("value", "")
        csrf_token = parsed.xpath("//meta[@name='csrf-token']")[0].get("content")
        con_key = await self.__access("Modifypw", url, require_conkey=False, csrf_token=csrf_token)
        payload = {
                "_token": token,
                "board_pw": password,
                "id": board_id,
                "no": document_id,
                "mode": "modify",
                "con_key": con_key,
                }
        header = XML_HTTP_REQ_HEADERS.copy()
        header["Referer"] = referer
        header["Host"] = "m.dcinside.com"
        header["Origin"] = "https://m.dcinside.com"
        header["X-CSRF-TOKEN"] = csrf_token
        url = "https://m.dcinside.com/ajax/pwcheck-board"
        async with self.session.post(url, headers=header, data=payload) as res:
            res = await res.text()
            if not res.strip():
                Exception("Error while modifing: maybe the password is incorrect")
        payload = {
                "board_pw": password,
                "id": board_id,
                "no": document_id,
                "_token": csrf_token
                }
        header = POST_HEADERS.copy()
        header["Referer"] = referer
        url = "https://m.dcinside.com/write/{}/modify/{}".format(board_id, document_id)
        async with self.session.post(url, headers=header, data=payload) as res:
            return await self.__write_or_modify_document(board_id, title, contents, name, password, intermediate=await res.text(), intermediate_referer=url, document_id=document_id)
    async def remove_document(self, board_id, document_id, password="", is_minor=False):
        if not password:
            url = "https://m.dcinside.com/board/{}/{}".format(board_id, document_id)
            async with self.session.get(url) as res:
                parsed = lxml.html.fromstring(await res.text())
            csrf_token = parsed.xpath("//meta[@name='csrf-token']")[0].get("content")
            header = XML_HTTP_REQ_HEADERS.copy()
            header["Referer"] = url
            header["X-CSRF-TOKEN"] = csrf_token
            con_key = await self.__access("board_Del", url, require_conkey=False, csrf_token=csrf_token)
            url = "https://m.dcinside.com/del/board"
            payload = { "id": board_id, "no": document_id, "con_key": con_key }
            async with self.session.post(url, headers=header, data=payload) as res:
                res = await res.text()
            if res.find("true") < 0:
                raise Exception("Error while removing: " + unquote(str(res)))
            return True
        url = "https://m.dcinside.com/confirmpw/{}/{}?mode=del".format(board_id, document_id)
        referer = url
        async with self.session.get(url) as res:
            parsed = lxml.html.fromstring(await res.text())
        token = parsed.xpath("//input[@name='_token']")[0].get("value", "")
        csrf_token = parsed.xpath("//meta[@name='csrf-token']")[0].get("content")
        board_name = parsed.xpath("//a[@class='gall-tit-lnk']")[0].text.strip()
        con_key = await self.__access("board_Del", url, require_conkey=False, csrf_token=csrf_token)
        payload = {
                "_token": token,
                "board_pw": password,
                "id": board_id,
                "no": document_id,
                "mode": "del",
                "con_key": con_key,
                }
        header = XML_HTTP_REQ_HEADERS.copy()
        header["Referer"] = url
        header["X-CSRF-TOKEN"] = csrf_token
        cookies = {
            "m_dcinside_" + board_id: board_id,
            "m_dcinside_lately": quote(board_id + "|" + board_name + ","),
            "_ga": "GA1.2.693521455.1588839880",
            }
        url = "https://m.dcinside.com/del/board"
        async with self.session.post(url, headers=header, data=payload, cookies=cookies) as res:
            res = await res.text()
        if res.find("true") < 0:
            raise Exception("Error while removing: " + unquote(str(res)))
        return True
    async def write_document(self, board_id, title="", contents="", name="", password="", is_minor=False):
        return await self.__write_or_modify_document(board_id, title, contents, name, password, is_minor=is_minor)

    async def prepare_write_document_pc(self, board_id, title="", contents="", name="", password="", use_html=False):
        return await self.__prepare_pc_write_document(board_id, title, contents, name, password, use_html)

    async def write_document_pc(self, board_id, title="", contents="", name="", password="", use_html=False):
        submit_url, payload = await self.__prepare_pc_write_document(board_id, title, contents, name, password, use_html)
        headers = PC_AJAX_HEADERS.copy()
        headers["Referer"] = "https://gall.dcinside.com/board/write/?id={}".format(board_id)
        async with self.session.post(submit_url, headers=headers, data=payload) as res:
            status = res.status
            final_url = str(res.url)
            text = await res.text()
        return self.__parse_pc_write_response(board_id, status, final_url, text)

    async def prepare_modify_document_pc(self, board_id, document_id, title="", contents="", password=""):
        return await self.__prepare_pc_modify_document(board_id, document_id, title, contents, password)

    async def modify_document_pc(self, board_id, document_id, title="", contents="", password=""):
        submit_url, payload = await self.__prepare_pc_modify_document(board_id, document_id, title, contents, password)
        headers = PC_AJAX_HEADERS.copy()
        headers["Referer"] = "https://gall.dcinside.com/board/modify/?id={}&no={}".format(board_id, document_id)
        async with self.session.post(submit_url, headers=headers, data=payload) as res:
            status = res.status
            final_url = str(res.url)
            text = await res.text()
        return self.__parse_pc_modify_response(board_id, document_id, status, final_url, text)

    async def __prepare_pc_write_document(self, board_id, title="", contents="", name="", password="", use_html=False):
        write_url = "https://gall.dcinside.com/board/write/?id={}".format(board_id)
        async with self.session.get(write_url, headers=PC_GET_HEADERS) as res:
            write_html = await res.text()
        parsed = lxml.html.fromstring(write_html)
        forms = parsed.xpath("//form[@id='write']")
        if not forms:
            snippet = " ".join(write_html.strip().split())[:500]
            raise Exception("Error while preparing pc write document: write form not found response={!r}".format(snippet))

        form = forms[0]
        payload = self.__serialize_pc_write_form(form)
        self.__set_pc_payload_value(payload, "id", board_id)
        self.__set_pc_payload_value(payload, "subject", title)
        self.__set_pc_payload_value(payload, "password", password)
        if use_html:
            self.__set_pc_payload_value(payload, "use_html", "Y")
        if name:
            self.__set_pc_payload_value(payload, "use_gall_nick", "N")
            self.__set_pc_payload_value(payload, "name", name)
        else:
            self.__set_pc_payload_value(payload, "use_gall_nick", "Y")
            self.__set_pc_payload_value(payload, "name", "")

        service_code = self.__pc_payload_value(payload, "service_code") or self.__pc_cookie("service_code")
        if service_code:
            self.__set_pc_payload_value(payload, "service_code", service_code)

        old_block_key = self.__pc_payload_value(payload, "block_key")
        await asyncio.sleep(PC_WRITE_MIN_WAIT_SECONDS)
        refreshed_block_key = await self.__pc_refresh_block_key(write_url, old_block_key)
        self.__set_pc_payload_value(
            payload,
            "service_code",
            self.__pc_apply_service_code_event_token(write_html, self.__pc_payload_value(payload, "service_code")),
        )

        payload.extend([
                ("ci_t", self.__pc_cookie("ci_c")),
                ("mode", "W"),
                ("movieIdx", ""),
                ("series_title", "[]"),
                ("series_data", ""),
                ("headTail", "\"\""),
                ("block_key", refreshed_block_key),
                ("memo", contents),
                ("code", self.__pc_payload_value(payload, "code")),
                ("bgm", "0"),
            ])

        submit_url = urljoin(write_url, form.get("action") or "/board/forms/article_submit")
        payload = [(key, "" if value is None else str(value)) for key, value in payload]
        return submit_url, payload

    async def __prepare_pc_modify_document(self, board_id, document_id, title="", contents="", password=""):
        if not password:
            raise Exception("Error while preparing pc modify document: password is required")
        modify_url = "https://gall.dcinside.com/board/modify/?id={}&no={}".format(board_id, document_id)
        async with self.session.get(modify_url, headers=PC_GET_HEADERS) as res:
            modify_html = await res.text()
        parsed = lxml.html.fromstring(modify_html)

        forms = parsed.xpath("//form[@id='modify']")
        if not forms:
            password_form = parsed.xpath("//form[@id='password_confirm']")
            if not password_form:
                snippet = " ".join(modify_html.strip().split())[:500]
                raise Exception("Error while preparing pc modify document: password form not found response={!r}".format(snippet))
            password_form = password_form[0]
            ci_t = self.__form_value(password_form, "ci_t") or self.__pc_cookie("ci_c")
            auth_token = self.__form_value(password_form, "auth_token")
            gallery_type = self.__pc_gallery_type(modify_html)
            password_headers = PC_AJAX_HEADERS.copy()
            password_headers["Referer"] = modify_url
            password_payload = {
                "id": board_id,
                "no": str(document_id),
                "_GALLTYPE_": gallery_type,
                "password": password,
                "g-recaptcha-response": "",
                "auth_token": auth_token,
                "ci_t": ci_t,
            }
            async with self.session.post(
                    "https://gall.dcinside.com/board/forms/modify_password_submit",
                    headers=password_headers,
                    data=password_payload) as res:
                password_text = (await res.text()).strip()
            password_parts = password_text.split("||")
            if not password_parts or password_parts[0].strip() != "true" or len(password_parts) < 2:
                raise Exception(
                    "Error while preparing pc modify document: password check failed response={!r}".format(
                        " ".join(password_text.split())[:500]
                    )
                )
            form_headers = PC_GET_HEADERS.copy()
            form_headers["Referer"] = modify_url
            form_payload = {
                "ci_t": ci_t,
                "id": board_id,
                "no": str(document_id),
                "key": password_parts[1].strip(),
            }
            async with self.session.post(modify_url, headers=form_headers, data=form_payload) as res:
                modify_html = await res.text()
            parsed = lxml.html.fromstring(modify_html)
            forms = parsed.xpath("//form[@id='modify']")

        if not forms:
            snippet = " ".join(modify_html.strip().split())[:500]
            raise Exception("Error while preparing pc modify document: modify form not found response={!r}".format(snippet))

        form = forms[0]
        current_contents = self.__pc_modify_contents(modify_html)
        payload = {
            "ci_t": self.__pc_cookie("ci_c"),
            "file": [],
            "file_write": [],
            "file_delete": [],
            "subject": title,
            "memo": contents,
            "id": self.__form_value(form, "id") or board_id,
            "r_key": self.__form_value(form, "r_key"),
            "key": self.__form_value(form, "key"),
            "no": self.__form_value(form, "no") or str(document_id),
            "bigdccon_key": self.__form_value(form, "bigdccon_key"),
            "upload_status": self.__form_value(form, "upload_status"),
            "headtext": self.__form_value(form, "headtext"),
            "bgm": self.__form_value(form, "bgm"),
            "g-recaptcha-response": "",
            "_GALLTYPE_": self.__form_value(form, "_GALLTYPE_") or self.__pc_gallery_type(modify_html),
            "poll": self.__form_value(form, "poll"),
            "origin_poll": self.__form_value(form, "origin_poll"),
            "s_pass": "",
            "auto_del_time": "",
            "fix": self.__form_value(form, "fix"),
            "noti_gall_ids": self.__form_value(form, "noti_gall_ids"),
            "canonical": self.__form_value(form, "canonical"),
            "secret": "",
            "movieIdx": "",
            "movie_exist_idx": "",
            "series_title": "[]",
            "series_data": "",
            "headTail": "\"\"",
            "my_auto_zzal_img": self.__form_value(form, "my_auto_zzal_img"),
        }
        if title == "":
            payload["subject"] = self.__form_value(form, "subject")
        if contents == "":
            payload["memo"] = current_contents
        submit_url = urljoin(modify_url, form.get("action") or "/board/forms/modify_submit")
        return submit_url, payload

    def __serialize_pc_write_form(self, form):
        payload = []
        for el in form.xpath(".//input[@name] | .//textarea[@name] | .//select[@name]"):
            name_attr = el.get("name")
            if not name_attr or el.get("disabled") is not None:
                continue
            input_type = (el.get("type") or "").lower()
            if input_type in ("button", "submit", "reset", "image", "file"):
                continue
            if input_type in ("checkbox", "radio") and el.get("checked") is None:
                continue
            if el.tag == "textarea":
                value = el.text or ""
            elif el.tag == "select":
                selected = el.xpath(".//option[@selected]")
                options = el.xpath(".//option")
                option = selected[0] if selected else (options[0] if options else None)
                value = option.get("value") if option is not None else ""
            else:
                value = el.get("value", "")
            payload.append((name_attr, "" if value is None else value))
        return payload

    def __form_value(self, form, name):
        nodes = form.xpath(".//*[@name=$name]", name=name)
        if not nodes:
            return ""
        node = nodes[0]
        if node.tag == "textarea":
            return node.text or ""
        return node.get("value", "") or ""

    def __pc_gallery_type(self, html):
        match = re.search(r"var\s+_GALLERY_TYPE_\s*=\s*\"([^\"]+)\"", html)
        return match.group(1) if match else "G"

    def __pc_modify_contents(self, html):
        match = re.search(r"let\s+modify_memo\s*=\s*\"((?:\\.|[^\"\\])*)\";", html)
        if not match:
            return ""
        try:
            return json.loads("\"{}\"".format(match.group(1)))
        except Exception:
            return match.group(1)

    def __pc_payload_value(self, payload, name):
        if isinstance(payload, dict):
            return payload.get(name, "")
        for key, value in payload:
            if key == name:
                return value
        return ""

    def __set_pc_payload_value(self, payload, name, value):
        for index, (key, _) in enumerate(payload):
            if key == name:
                payload[index] = (name, value)
                return
        payload.append((name, value))

    def __pc_cookie(self, name):
        cookies = self.session.cookie_jar.filter_cookies("https://gall.dcinside.com")
        cookie = cookies.get(name)
        return cookie.value if cookie else ""

    def __pc_apply_service_code_event_token(self, html, service_code):
        token_match = re.search(r"var\s+_r\s*=\s*_d\('([^']+)'\)", html)
        if not token_match or not service_code:
            return service_code
        decoded_token = self.__pc_decode_service_code_token(token_match.group(1))
        if not decoded_token:
            return service_code

        first_digit = int(decoded_token[0])
        first_digit = first_digit - 5 if first_digit > 5 else first_digit + 4
        decoded_token = str(first_digit) + decoded_token[1:]
        parts = decoded_token.split(",")
        replacement = ""
        for index, part in enumerate(parts):
            replacement += chr(int(2 * (float(part) - index - 1) / (13 - index - 1)))
        return service_code[:-10] + replacement

    def __pc_decode_service_code_token(self, token):
        token = re.sub(r"[^A-Za-z0-9+/=]", "", token)
        decoded = []
        index = 0
        while index < len(token):
            first = PC_SERVICE_CODE_ALPHABET.find(token[index])
            second = PC_SERVICE_CODE_ALPHABET.find(token[index + 1])
            third = PC_SERVICE_CODE_ALPHABET.find(token[index + 2])
            fourth = PC_SERVICE_CODE_ALPHABET.find(token[index + 3])
            index += 4
            if min(first, second, third, fourth) < 0:
                return ""
            decoded.append(chr((first << 2) | (second >> 4)))
            if third != 64:
                decoded.append(chr(((15 & second) << 4) | (third >> 2)))
            if fourth != 64:
                decoded.append(chr(((3 & third) << 6) | fourth))
        return "".join(decoded)

    async def __pc_refresh_block_key(self, referer, block_key):
        if not block_key:
            raise Exception("Error while preparing pc write document: block_key not found")
        csrf_token = self.__pc_cookie("ci_c")
        if not csrf_token:
            raise Exception("Error while preparing pc write document: ci_c cookie not found")
        headers = PC_AJAX_HEADERS.copy()
        headers["Referer"] = referer
        payload = {
                "ci_t": csrf_token,
                "block_key": block_key,
            }
        async with self.session.post("https://gall.dcinside.com/block/block/", headers=headers, data=payload) as res:
            text = (await res.text()).strip()
        if not text:
            raise Exception("Error while preparing pc write document: refreshed block_key is empty")
        return text

    def __parse_pc_write_response(self, board_id, status, final_url, text):
        parts = text.split("||")
        if parts and parts[0].strip() == "true":
            if len(parts) > 1 and parts[1].strip():
                return parts[1].strip()
            raise Exception(
                "Error while parsing pc write document: success response had no document id status={} url={} response={!r}".format(
                    status, final_url, " ".join(text.strip().split())[:500]
                )
            )
        if parts and parts[0].strip() == "false":
            reason = parts[1].strip() if len(parts) > 1 else ""
            raise Exception(
                "Error while write pc document: status={} url={} reason={!r} response={!r}".format(
                    status, final_url, reason, " ".join(text.strip().split())[:500]
                )
            )
        document_id_match = re.search(r"[?&]no=([0-9]+)", text)
        if document_id_match:
            return document_id_match.group(1)
        raise Exception(
            "Error while write pc document: status={} url={} response={!r}".format(
                status, final_url, " ".join(text.strip().split())[:500]
            )
        )

    def __parse_pc_modify_response(self, board_id, document_id, status, final_url, text):
        parts = text.split("||")
        if parts and parts[0].strip() == "true":
            if len(parts) > 1 and parts[1].strip():
                return parts[1].strip()
            return str(document_id)
        if parts and parts[0].strip() == "false":
            reason = parts[1].strip() if len(parts) > 1 else ""
            raise Exception(
                "Error while modify pc document: status={} url={} reason={!r} response={!r}".format(
                    status, final_url, reason, " ".join(text.strip().split())[:500]
                )
            )
        document_id_match = re.search(r"[?&]no=([0-9]+)", text)
        if document_id_match:
            return document_id_match.group(1)
        raise Exception(
            "Error while modify pc document: status={} url={} response={!r}".format(
                status, final_url, " ".join(text.strip().split())[:500]
            )
        )

    async def __write_or_modify_document(self, board_id, title="", contents="", name="", password="", intermediate=None, intermediate_referer=None, document_id=None, is_minor=False):
        if not intermediate:
            url = "https://m.dcinside.com/write/{}".format(board_id)
            async with self.session.get(url) as res:
                parsed = lxml.html.fromstring(await res.text())
        else:
            parsed = lxml.html.fromstring(intermediate)
            url = intermediate_referer
        first_url = url
        rand_code = parsed.xpath("//input[@name='code']")
        rand_code = rand_code[0].get("value") if len(rand_code) else None
        user_id_nodes = parsed.xpath("//input[@name='user_id']")
        user_id = user_id_nodes[0].get("value") if not name and user_id_nodes else None
        mobile_key = parsed.xpath("//input[@id='mobile_key']")[0].get("value")
        hide_robot = parsed.xpath("//input[@class='hide-robot']")[0].get("name")
        csrf_token = parsed.xpath("//meta[@name='csrf-token']")[0].get("content")
        con_key = await self.__access("dc_check2", url, require_conkey=False, csrf_token=csrf_token)
        board_name = parsed.xpath("//a[@class='gall-tit-lnk']")[0].text.strip()
        header = XML_HTTP_REQ_HEADERS.copy()
        header["Referer"] = url
        header["X-CSRF-TOKEN"] = csrf_token
        url = "https://m.dcinside.com/ajax/w_filter"
        payload = {
                "subject": title,
                "memo": contents,
                "mode": "write",
                "id": board_id,
                }
        if rand_code:
            payload["code"] = rand_code
        async with self.session.post(url, headers=header, data=payload) as res:
            res = await res.text()
            res = json.loads(res)
        if not res["result"]:
            raise Exception("Erorr while write document: " + str(res))
        header = POST_HEADERS.copy()
        url = "https://mupload.dcinside.com/write_new.php"
        header["Host"] = "mupload.dcinside.com"
        header["Origin"] = "https://m.dcinside.com"
        header["Referer"] = first_url
        payload = {}
        for input_el in parsed.xpath("//form[@id='writeForm']//input[@name]"):
            name_attr = input_el.get("name")
            if not name_attr or input_el.get("disabled") is not None:
                continue
            if input_el.get("type") in ("checkbox", "radio") and input_el.get("checked") is None:
                continue
            payload[name_attr] = input_el.get("value", "")
        for textarea in parsed.xpath("//form[@id='writeForm']//textarea[@name]"):
            name_attr = textarea.get("name")
            if name_attr and textarea.get("disabled") is None:
                payload[name_attr] = textarea.text or ""
        payload.update({
                "subject": title,
                "memo": contents,
                hide_robot: "1",
                "GEY3JWF": hide_robot,
                "id": board_id,
                "mode": "write",
                "Block_key": con_key,
                "is_minor": "1" if is_minor else "",
                "GEY3JWF": hide_robot,
            })
        if rand_code:
            payload["code"] = rand_code
        if name:
            payload["name"] = name
            payload["use_gall_nickname"] = "0"
        if password:
            payload["password"] = password
        if user_id:
            payload["user_id"] = user_id
        if intermediate:
            payload["mode"] = "modify"
            payload["delcheck"] = ""
            payload["t_ch2"] = ""
            payload["no"] = document_id
        cookies = {
            "m_dcinside_" + board_id: board_id,
                "m_dcinside_lately": quote(board_id + "|" + board_name + ","),
                "_ga": "GA1.2.693521455.1588839880",
            }
        form = aiohttp.FormData()
        form._is_multipart = True
        for key, value in payload.items():
            form.add_field(key, "" if value is None else str(value))
        async with self.session.post(url, headers=header, data=form, cookies=cookies) as res:
            status = res.status
            final_url = str(res.url)
            text = await res.text()
        return self.__parse_write_response(board_id, status, final_url, text)

    def __parse_write_response(self, board_id, status, final_url, text):
        document_id_match = re.search(r"/board/{}/([0-9]+)".format(re.escape(board_id)), final_url)
        if document_id_match:
            return document_id_match.group(1)
        document_id_match = re.search(r"/board/{}/([0-9]+)".format(re.escape(board_id)), text)
        if document_id_match:
            return document_id_match.group(1)
        document_id_match = re.search(r"[?&]no=([0-9]+)", text)
        if document_id_match:
            return document_id_match.group(1)
        alert_match = re.search(r"alert\\(['\\\"](.+?)['\\\"]\\)", text)
        alert = unquote(alert_match.group(1)) if alert_match else None
        snippet = " ".join(text.strip().split())[:500]
        if alert:
            snippet = "{} | {}".format(alert, snippet)
        raise Exception(
            "Error while write document: status={} url={} response={!r}".format(
                status, final_url, snippet
            )
        )

    async def __access(self, token_verify, target_url, require_conkey=True, csrf_token=None):
        if require_conkey:
            async with self.session.get(target_url) as res:
                parsed = lxml.html.fromstring(await res.text())
            con_key = parsed.xpath("//input[@id='con_key']")[0].get("value")
            payload = { "token_verify": token_verify, "con_key": con_key }
        else:
            payload = { "token_verify": token_verify, }
        url = "https://m.dcinside.com/ajax/access"
        headers = XML_HTTP_REQ_HEADERS.copy()
        headers["Referer"] = target_url
        headers["X-CSRF-TOKEN"] = csrf_token
        async with self.session.post(url, headers=headers, data=payload) as res:
            return (await res.json())["Block_key"]
    def __parse_time(self, time): 
        today = datetime.now() 
        if len(time) <= 5: 
            if time.find(":") > 0:
                return datetime.strptime(time, "%H:%M").replace(year=today.year, month=today.month, day=today.day)
            else:
                return datetime.strptime(time, "%m.%d").replace(year=today.year, hour=23, minute=59, second=59)
        elif len(time) <= 11:
            if time.find(":") > 0:
                return datetime.strptime(time, "%m.%d %H:%M").replace(year=today.year)
            else:
                return datetime.strptime(time, "%y.%m.%d").replace(year=today.year, hour=23, minute=59, second=59)
        elif len(time) <= 16:
            if time.count(".") >= 2:
                return datetime.strptime(time, "%Y.%m.%d %H:%M")
            else:
                return datetime.strptime(time, "%m.%d %H:%M:%S").replace(year=today.year)
        else:
            if "." in time:
                return datetime.strptime(time, "%Y.%m.%d %H:%M:%S")
            else:
                return datetime.strptime(time, "%Y-%m-%d %H:%M:%S")

import unittest
import sys

# Check version info
version = sys.version_info
if version.major >= 3 and version.minor >= 8:
    class Test(unittest.IsolatedAsyncioTestCase):
        def setUp(self):
            pass
        async def asyncSetUp(self):
            self.api = API()
        async def asyncTearDown(self):
            await self.api.close()
        async def test_async_with(self):
            async with API() as api:
                doc = api.board(board_id='aoegame', num=1).__anext__()
                self.assertNotEqual(doc, None)
        async def test_read_minor_board_one(self):
            async for doc in self.api.board(board_id='aoegame', num=1):
                for attr in doc.__slots__:
                    if attr == 'subject': continue
                    val = getattr(doc, attr)
                    self.assertNotEqual(val, None, attr)
                    self.assertNotEqual(val, '', attr)
                self.assertGreater(doc.time, datetime.now() - timedelta(hours=1))
                self.assertLess(doc.time, datetime.now() + timedelta(hours=1))
        async def test_read_minor_board_many(self):
            count = 0
            async for doc in self.api.board(board_id='aoegame', num=201):
                for attr in doc.__slots__:
                    if attr == 'subject': continue
                    val = getattr(doc, attr)
                    self.assertNotEqual(val, None, attr)
                    self.assertNotEqual(val, '', attr)
                count += 1
                self.assertGreater(doc.time, datetime.now() - timedelta(hours=1))
                self.assertLess(doc.time, datetime.now() + timedelta(hours=1))
            self.assertAlmostEqual(count, 201)
        async def test_read_major_comment(self):
            comms = ' '.join([str(comm) async for comm in self.api.comments(board_id='programming', document_id=1847628)])
            self.assertEqual(comms, 'ㄴ ㅇㅇ(112.172): 뭐하러일함  - dc App | 2021-08-21 12:28:00 ㄴ ㅇㅇ(39.121): 나였으면 뒤질때까지 디씨질만 함 | 2021-08-21 12:32:00 ㄴㄴ ㅇㅇ(202.150): 심심한 인생 | 2021-08-21 12:40:00 ㄴㄴ ㅇㅇ(39.121): 난 디씨질이 세상에서 젤 재밌어 | 2021-08-21 12:42:00 ㄴ ㅇㅇ(202.150): 저건 그냥 부자인데 ㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋ | 2021-08-21 12:45:00')
        async def test_read_minor_recent_comments(self):
            async for doc in self.api.board(board_id='aoegame'):
                comments = [comm async for comm in doc.comments()]
                if not comments: continue
                for comm in comments:
                    for attr in comm.__slots__:
                        if attr in ['contents', 'dccon', 'voice', 'author_id']: continue
                        val = getattr(comm, attr)
                        self.assertNotEqual(val, None, attr)
                        self.assertNotEqual(val, '', attr)
                    self.assertNotEqual(comm.contents or comm.dccon or comm.voice, None)
                    self.assertGreater(comm.time, datetime.now() - timedelta(hours=1))
                    self.assertLess(comm.time, datetime.now() + timedelta(hours=1))
                break
        async def test_read_board_one(self):
            async for doc in self.api.board(board_id='programming', num=1):
                for attr in doc.__slots__:
                    if attr == 'subject': continue
                    val = getattr(doc, attr)
                    self.assertNotEqual(val, None, attr)
                    self.assertNotEqual(val, '', attr)
                self.assertGreater(doc.time, datetime.now() - timedelta(hours=24))
                self.assertLess(doc.time, datetime.now() + timedelta(hours=1))
        async def test_read_board_many(self):
            count = 0
            async for doc in self.api.board(board_id='programming', num=201):
                for attr in doc.__slots__:
                    if attr == 'subject': continue
                    val = getattr(doc, attr)
                    self.assertNotEqual(val, None, attr)
                    self.assertNotEqual(val, '', attr)
                count += 1
                self.assertGreater(doc.time, datetime.now() - timedelta(hours=24))
                self.assertLess(doc.time, datetime.now() + timedelta(hours=1))
            self.assertAlmostEqual(count, 201)
        async def test_read_recent_comments(self):
            async for doc in self.api.board(board_id='aoegame'):
                comments = [comm async for comm in doc.comments()]
                if not comments: continue
                for comm in comments:
                    for attr in comm.__slots__:
                        if attr in ['contents', 'dccon', 'voice', 'author_id']: continue
                        val = getattr(comm, attr)
                        self.assertNotEqual(val, None, attr)
                        self.assertNotEqual(val, '', attr)
                    self.assertNotEqual(comm.contents or comm.dccon or comm.voice, None)
                    self.assertGreater(comm.time, datetime.now() - timedelta(hours=24))
                    self.assertLess(comm.time, datetime.now() + timedelta(hours=1))
                break
        async def test_minor_document(self):
            doc = await (await self.api.board(board_id='aoegame', num=1).__anext__()).document()
            self.assertNotEqual(doc, None)
            for attr in doc.__slots__:
                if attr in ['author_id', 'subject']: continue
                val = getattr(doc, attr)
                self.assertNotEqual(val, None, attr)
                self.assertNotEqual(val, '', attr)
            self.assertGreater(doc.time, datetime.now() - timedelta(hours=1))
            self.assertLess(doc.time, datetime.now() + timedelta(hours=1))
        async def test_document(self):
            doc = await (await self.api.board(board_id='programming', num=1).__anext__()).document()
            self.assertNotEqual(doc, None)
            for attr in doc.__slots__:
                if attr in ['author_id', 'subject']: continue
                val = getattr(doc, attr)
                self.assertNotEqual(val, None, attr)
            self.assertGreater(doc.time, datetime.now() - timedelta(hours=1))
            self.assertLess(doc.time, datetime.now() + timedelta(hours=1))
        '''
        async def test_write_mod_del_document_comment(self):
            board_id='programming'
            doc_id = await self.api.write_document(board_id=board_id, title="제목", contents="내용", name="닉네임", password="비밀번호")
            doc = await self.api.document(board_id=board_id, document_id=doc_id)
            self.assertEqual(doc.contents, "내용")
            doc_id = await self.api.modify_document(board_id=board_id, document_id=doc_id, title="수정된 제목", contents="수정된 내용", name="수정된 닉네임", password="비밀번호")
            doc = await self.api.document(board_id=board_id, document_id=doc_id)
            self.assertEqual(doc.contents, "수정된 내용")
            comm_id = await self.api.write_comment(board_id=board_id, document_id=doc_id, contents="댓글", name="닉네임", password="비밀번호")
            doc = await self.api.document(board_id=board_id, document_id=doc_id)
            comm = await doc.comments().__anext__()
            self.assertEqual(comm.contents, "댓글")
            await self.api.remove_document(board_id=board_id, document_id=doc_id, password="비밀번호")
            doc = await self.api.document(board_id=board_id, document_id=doc_id)
            self.assertEqual(doc, None)
        async def test_minor_write_mod_del_document_comment(self):
            board_id='stick'
            doc_id = await self.api.write_document(board_id=board_id, title="제목", contents="내용", name="닉네임", password="비밀번호", is_minor=True)
            doc = await self.api.document(board_id=board_id, document_id=doc_id)
            self.assertEqual(doc.contents, "내용")
            doc_id = await self.api.modify_document(board_id=board_id, document_id=doc_id, title="수정된 제목", contents="수정된 내용", name="수정된 닉네임", password="비밀번호", is_minor=True)
            doc = await self.api.document(board_id=board_id, document_id=doc_id)
            self.assertEqual(doc.contents, "수정된 내용")
            comm_id = await self.api.write_comment(board_id=board_id, document_id=doc_id, contents="댓글", name="닉네임", password="비밀번호")
            doc = await self.api.document(board_id=board_id, document_id=doc_id)
            comm = await doc.comments().__anext__()
            self.assertEqual(comm.contents, "댓글")
            await self.api.remove_document(board_id=board_id, document_id=doc_id, password="비밀번호")
            doc = await self.api.document(board_id=board_id, document_id=doc_id)
            self.assertEqual(doc, None)
        '''

if __name__ == "__main__":
    unittest.main()
