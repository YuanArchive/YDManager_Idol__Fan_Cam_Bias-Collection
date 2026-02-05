# -*- coding: utf-8 -*-
import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

results = []
results.append("=== global_files 구조 분석 ===")

# 글로벌 캐시 직접 로드
with open("video_global_cache.json", "r", encoding="utf-8") as f:
    global_files = json.load(f)

results.append(f"총 파일 수: {len(global_files)}")
results.append("")

# 필드 분석
for i, item in enumerate(global_files[:5]):
    results.append(f"[{i}] 필드 분석:")
    results.append(f"  - name: {item.get('name', '[없음]')[:50]}...")
    results.append(f"  - text: {item.get('text', '[없음]')[:50]}...")
    results.append(f"  - path: {item.get('path', '[없음]')[-50:]}...")
    results.append("")

# "이"가 포함된 파일 중 text 필드 없는 경우 확인
results.append("=== 'text' 필드가 없는 파일 ===")
no_text_count = 0
for item in global_files:
    if 'text' not in item:
        no_text_count += 1
        name = item.get('name', '')
        if no_text_count <= 5:
            results.append(f"  - {name[:50]}...")

results.append(f"총 {no_text_count}개 파일에 'text' 필드 없음")
results.append("")
results.append("=== 완료 ===")

# 결과 저장
with open("debug_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))

print("결과가 debug_result.txt에 저장됨")
