#!/bin/sh
# 시험 여럿을 차례로 돌리고 줄여서 보여 준다. 한 시험은 9분 안에 끝나야 한다(timeout 이 게임까지 끝낸다).
# 사용: sh run_suite.sh "<시험 파일> <인자…>" "<시험 파일> <인자…>" …      (첫 인자 = 결과 이름)
cd "$(dirname "$0")" || exit 1
OUT=/y/AI/forest-qol-test-rewind/out
for spec in "$@"; do
  set -- $spec
  name=$2
  echo "=== $spec  ($(date +%H:%M:%S))"
  PYTHONIOENCODING=utf-8 timeout 535 python -I "$@" > "$OUT/$name.console.txt" 2>&1
  code=$?
  log="$OUT/$name/run.log"
  echo "    exit $code, PASS $(grep -c ' PASS ' "$log" 2>/dev/null), FAIL $(grep -c ' FAIL ' "$log" 2>/dev/null), compares $(grep -c '  compare ' "$log" 2>/dev/null), differing $(grep '  compare ' "$log" 2>/dev/null | grep -c 'diff pixels [1-9]')"
  grep -h ' FAIL \|RESULT\|partly empty\|the same when taken again\|normal quit\|exit code\|verify .* DIFF' "$log" 2>/dev/null | cut -c1-260
  grep -h 'Traceback\|Error\|assert' "$OUT/$name.console.txt" | cut -c1-200
done
echo "=== done ($(date +%H:%M:%S))"
