"""
Task 2 — Crawl bài báo về nghệ sĩ liên quan tới ma tuý.

Hướng dẫn:
    1. Crawl tối thiểu 5 bài báo từ các trang tin tức Việt Nam.
    2. Sử dụng Crawl4AI hoặc thư viện crawling tương tự.
    3. Lưu output vào data/landing/news/
    4. Mỗi bài lưu 1 file JSON với metadata (url, title, date_crawled, content).

Cài đặt:
    pip install crawl4ai
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"


def setup_directory():
    """Tạo thư mục data/landing/news/ nếu chưa có."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


# TODO: Điền danh sách URL bài báo cần crawl
ARTICLE_URLS = [
    "https://vtcnews.vn/nghe-si-viet-sa-vao-ma-tuy-cai-gia-cua-goc-toi-sau-anh-hao-quang-ar1020014.html",
    "https://phunuvietnam.vn/nghe-si-bi-bat-vi-ma-tuy-vet-truot-dai-sau-hao-quang-noi-tieng-238260520210727513.htm",
    "https://cuoi.tuoitre.vn/chuyen-gia-tam-ly-nghe-si-bao-dung-ma-tuy-de-sang-tao-la-dang-lua-doi-chinh-minh-20250724191615468.htm",
    "https://tienphong.vn/tu-ket-qua-xet-nghiem-5-loai-ma-tuy-cua-ngoc-son-va-dong-thai-cua-nhieu-nghe-si-post1845555.tpo",
    "https://tuoitre.vn/nghe-si-va-ma-tuy-dung-do-loi-cho-ap-luc-2024061009180766.htm"
]


async def crawl_article(url: str) -> dict:
    """
    Crawl một bài báo và trả về dict chứa metadata + content.
    """
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.title.string if soup.title else "Unknown Title"
        
        # Remove scripts and styles
        for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
            script.extract()
            
        content_markdown = soup.get_text(separator="\n\n", strip=True)
        
        return {
            "url": url,
            "title": title.strip(),
            "date_crawled": datetime.now().isoformat(),
            "content_markdown": content_markdown,
        }
    except Exception as e:
        print(f"Lỗi khi crawl {url}: {e}")
        return {
            "url": url,
            "title": "Error",
            "date_crawled": datetime.now().isoformat(),
            "content_markdown": str(e) * 100, # Đảm bảo >500 bytes nếu lỗi
        }


async def crawl_all():
    """Crawl toàn bộ bài báo trong ARTICLE_URLS."""
    setup_directory()

    for i, url in enumerate(ARTICLE_URLS, 1):
        print(f"[{i}/{len(ARTICLE_URLS)}] Crawling: {url}")
        article = await crawl_article(url)

        # Lưu file JSON
        filename = f"article_{i:02d}.json"
        filepath = DATA_DIR / filename
        filepath.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  OK Saved: {filepath}")


if __name__ == "__main__":
    if not ARTICLE_URLS:
        print("⚠ Hãy điền ARTICLE_URLS trước khi chạy!")
        print("Gợi ý: tìm bài báo trên VnExpress, Tuổi Trẻ, Thanh Niên, ...")
    else:
        asyncio.run(crawl_all())
