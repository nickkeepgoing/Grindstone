"""
grindstone_client.py
ใช้ดึง prompts จาก Go backend แล้วเอาไปให้ LLM
ใช้แค่ stdlib (urllib) ไม่ต้องลง requests ก็ได้
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any


@dataclass
class GrindstoneClient:
    base_url: str = "http://localhost:8080"
    timeout: float = 30.0

    def _post(self, path: str, payload: dict) -> Any:
        req = urllib.request.Request(
            url=f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code}: {body}") from e

    def _get(self, path: str) -> Any:
        with urllib.request.urlopen(
            f"{self.base_url}{path}", timeout=self.timeout
        ) as resp:
            return json.loads(resp.read().decode("utf-8"))

    # --- public API ---

    def health(self) -> dict:
        return self._get("/health")

    def categories(self) -> list[dict]:
        """รายการ category ทั้งหมด + จำนวน prompt ที่โหลดได้"""
        return self._get("/categories")

    def sample(
        self,
        total: int,
        weights: dict[str, float],
        seed: int | None = None,
    ) -> dict:
        """
        สุ่ม prompts ตาม % ที่กำหนด

        Args:
            total: จำนวน prompt รวมที่ต้องการ
            weights: เช่น {"owasp": 50, "thai": 30, "public": 20}
                     ผลรวมต้องได้ 100
            seed: ใส่เพื่อให้ผลซ้ำกันได้ (reproducible)

        Returns:
            {
              "total": int,
              "sampled": [{"id", "category", "text", "tags", "meta"}, ...],
              "breakdown": {category: count},
              "requested": {category: count},
              "warnings": [str, ...]
            }
        """
        payload: dict[str, Any] = {"total": total, "weights": weights}
        if seed is not None:
            payload["seed"] = seed
        return self._post("/sample", payload)


# ----- ตัวอย่างการใช้งาน -----
if __name__ == "__main__":
    client = GrindstoneClient()

    print("== Health ==")
    print(client.health())

    print("\n== Categories ==")
    for c in client.categories():
        print(f"  {c['name']:8s} loaded={c['loaded']:5d} / expected={c['expected']}")

    print("\n== Sampling 10 prompts (40% owasp, 30% thai, 20% public, 10% mitre) ==")
    result = client.sample(
        total=10,
        weights={"owasp": 40, "thai": 30, "public": 20, "mitre": 10},
        seed=42,
    )
    print(f"got {result['total']} prompts")
    print(f"breakdown: {result['breakdown']}")
    if result.get("warnings"):
        print(f"warnings: {result['warnings']}")

    print("\n== Prompts ==")
    for p in result["sampled"]:
        print(f"  [{p['category']:6s}] {p['id']}: {p['text'][:80]}")

    # ส่งต่อเข้า LLM ตามต้องการ เช่น:
    # for p in result["sampled"]:
    #     response = call_target_llm(p["text"])
    #     evaluate(p, response)
