"""Grounded answer builders for the Day 8 agents."""

from __future__ import annotations

import json
from collections import deque
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from Lab_Assigment.common.llm import get_llm, llm_enabled
from Lab_Assigment.rag.retrieval import build_source_list, format_hits, retrieve_domain, source_label


def _trim_excerpt(text: str, limit: int = 240) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."


def build_domain_fallback(question: str, domain: str, hits: list[dict[str, Any]]) -> str:
    section_title = "Cơ sở pháp lý liên quan" if domain == "legal" else "Tin tức và dữ kiện liên quan"
    intro = (
        "Không tìm thấy trích đoạn đủ mạnh trong corpus hiện có."
        if not hits else
        "Dưới đây là các trích đoạn liên quan nhất từ knowledge base cục bộ."
    )

    lines = [f"## {section_title}", intro, f"Câu hỏi: {question}"]
    if hits:
        lines.append("### Trích đoạn nổi bật")
        for hit in hits[:3]:
            lines.append(f"- [{source_label(hit)}] {_trim_excerpt(hit['content'])}")
    lines.append("### Ghi chú")
    lines.append(
        "Phần trả lời này được dựng từ retrieval cục bộ và nên được dùng như tài liệu tham khảo ban đầu."
    )
    return "\n".join(lines)


def build_domain_answer(question: str, domain: str, hits: list[dict[str, Any]]) -> str:
    fallback = build_domain_fallback(question, domain, hits)
    if not hits or not llm_enabled():
        return fallback

    system_prompt = (
        "Bạn là trợ lý pháp lý chuyên trả lời bằng tiếng Việt. "
        "Chỉ sử dụng context được cung cấp. Mỗi nhận định phải gắn citation dạng "
        "[ten_nguon, chunk X]. Nếu context không đủ, nói rõ là chưa xác minh đủ."
    )
    user_prompt = (
        f"Question: {question}\n\n"
        f"Context:\n{format_hits(hits, max_excerpt=500)}\n\n"
        "Hãy trả lời ngắn gọn, rõ ràng, có mục 'Nguồn trích dẫn'."
    )

    try:
        response = get_llm().invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        return response.content if response.content else fallback
    except Exception:
        return fallback


def build_specialist_response(question: str, domain: str, top_k: int = 4) -> dict[str, Any]:
    hits = retrieve_domain(question, domain, top_k=top_k)
    answer = build_domain_answer(question, domain, hits)
    return {
        "domain": domain,
        "question": question,
        "answer": answer,
        "retrieval_mode": hits[0]["source"] if hits else "none",
        "sources": build_source_list(hits),
        "evidence": [
            {
                "citation": source_label(hit),
                "excerpt": _trim_excerpt(hit["content"], limit=180),
                "score": round(hit["score"], 4),
            }
            for hit in hits[:4]
        ],
    }


def parse_specialist_payload(raw_text: str, domain: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_text)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {
        "domain": domain,
        "question": "",
        "answer": raw_text,
        "retrieval_mode": "unknown",
        "sources": [],
        "evidence": [],
    }


def format_memory_context(history: deque[dict[str, str]]) -> str:
    if not history:
        return "Chưa có lịch sử hội thoại."
    lines = []
    for item in history:
        lines.append(f"- Q: {item['question']}")
        lines.append(f"  A: {_trim_excerpt(item['answer'], limit=220)}")
    return "\n".join(lines)


def build_aggregate_fallback(
    question: str,
    legal_payload: dict[str, Any] | None,
    news_payload: dict[str, Any] | None,
    memory_context: str,
) -> str:
    lines = [
        "# Tu van phap ly ket hop RAG",
        f"## Cau hoi\n{question}",
        f"## Ngu canh hoi thoai\n{memory_context}",
    ]
    if legal_payload:
        lines.append("## Co so phap ly")
        lines.append(legal_payload.get("answer", "Khong co phan tich phap ly."))
    if news_payload:
        lines.append("## Tin tuc lien quan")
        lines.append(news_payload.get("answer", "Khong co du kien tu nhom tin tuc."))
    lines.append("## Tom tat")
    if legal_payload and news_payload:
        lines.append(
            "Tra loi nay ket hop ca van ban phap luat va cac bai viet lien quan trong corpus hien co."
        )
    elif legal_payload:
        lines.append("Tra loi nay duoc tong hop chu yeu tu van ban phap luat trong corpus.")
    elif news_payload:
        lines.append("Tra loi nay duoc tong hop chu yeu tu cac bai viet tin tuc trong corpus.")
    else:
        lines.append("He thong hien chua tim duoc nguon phu hop trong corpus.")
    lines.append("## Luu y")
    lines.append("Noi dung chi mang tinh tham khao hoc tap, khong thay the tu van cua luat su co giay phep.")
    return "\n\n".join(lines)


def build_aggregate_answer(
    question: str,
    legal_payload: dict[str, Any] | None,
    news_payload: dict[str, Any] | None,
    memory_context: str,
) -> str:
    fallback = build_aggregate_fallback(question, legal_payload, news_payload, memory_context)
    if not llm_enabled():
        return fallback

    sections = []
    if legal_payload:
        sections.append(f"### Legal\n{legal_payload.get('answer', '')}")
    if news_payload:
        sections.append(f"### News\n{news_payload.get('answer', '')}")
    if not sections:
        return fallback

    prompt = (
        "Ban la chat bot tu van phap ly bang tieng Viet. Tong hop phan phan tich sau thanh "
        "mot cau tra loi co cau truc, giu citation neu da co, va ket thuc bang disclaimer ngan.\n\n"
        f"Question: {question}\n\n"
        f"Conversation memory:\n{memory_context}\n\n"
        f"{chr(10).join(sections)}"
    )
    try:
        response = get_llm().invoke([
            SystemMessage(content="Chi su dung thong tin duoc cung cap. Khong bo sung thong tin khong co trong context."),
            HumanMessage(content=prompt),
        ])
        return response.content if response.content else fallback
    except Exception:
        return fallback

