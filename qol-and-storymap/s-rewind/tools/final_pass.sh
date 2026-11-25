#!/bin/sh
# 통합 빌드(P:\AI\forest-qol\build\ForestChart.dll)를 시험 사본에 넣고 되감기 시험을 모두 돌린다. 줄여서 보여 주고, 자세한 것은 out\<이름>\ 에 남는다.
# 세 묶음: 1배 창(화면 모듈 끔) → 화면 모듈 켬(알림·안내, 타이틀로 돌아가기) → 4K 창(화면·4K 글자·4K 그림 켬).
# 한 시험은 9분 안에 끝나야 한다(timeout 이 게임까지 끝낸다). 중간에 멈출 때는 sh·timeout·python·시험 사본의 Forest.exe 가 남으니 프로세스를 확인해 끝낼 것.
# 사용: sh final_pass.sh <이름 머리글자>     예) sh final_pass.sh j  → j3 j7 j11a j5 j18 j13 j17a j17b j11k j20 j6
P=${1:-z}
cd "$(dirname "$0")" || exit 1
OUT=/y/AI/forest-qol-test-rewind/out
DLL="dll=P:/AI/forest-qol/build/ForestChart.dll"

run() {
  name=$1; shift
  echo "=== $name: $*  ($(date +%H:%M:%S))"
  PYTHONIOENCODING=utf-8 timeout 535 "$@" > "$OUT/$name.console.txt" 2>&1
  code=$?
  log="$OUT/$name/run.log"
  echo "    exit $code, PASS $(grep -c ' PASS ' "$log" 2>/dev/null), FAIL $(grep -c ' FAIL ' "$log" 2>/dev/null), compares $(grep -c '  compare .* diff pixels' "$log" 2>/dev/null), differing $(grep '  compare ' "$log" 2>/dev/null | grep -c 'diff pixels [1-9]')"
  grep -h ' FAIL \|partly empty\|the same when taken again\|normal quit\|exit code\|verify .* DIFF\|request dropped' "$log" 2>/dev/null | cut -c1-240
  grep -h 'RESULT\|Traceback\|Error\|assert' "$OUT/$name.console.txt" | cut -c1-200
}

echo "##### 1x window, screen module off"
python -I prep_copy.py "$DLL" present=0 hitext=0 hiart=0 present_test_shift_x=0 play_log=0 hiart_log=0 | head -n 1
run ${P}3 python -I t3_paths.py ${P}3
run ${P}7 python -I t7_audio.py ${P}7
run ${P}11a python -I t11_units.py ${P}11a 52 0 2100:1336,2100:6692,2100:7754 2100:6692 2100:4966
run ${P}5 python -I t5_fidelity.py ${P}5 60 30
run ${P}18 python -I t18_hidden.py ${P}18

echo "##### screen module on (notices, key guide), 1x window by the window menu"
python -I prep_copy.py "$DLL" present=1 hitext=0 hiart=0 present_test_shift_x=0 play_log=1 hiart_log=0 | head -n 1
run ${P}13 python -I t13_formal.py ${P}13 38
run ${P}17a python -I t17_title_return.py ${P}17a 5 alte
run ${P}17b python -I t17_title_return.py ${P}17b 2 goto

echo "##### 4K window: screen module, 4K text and 4K art on"
python -I prep_copy.py "$DLL" present=1 hitext=1 hiart=1 present_test_shift_x=0 play_log=0 hiart_log=0 | head -n 1
run ${P}11k env T11_SETTLE=1.6 T11_SHOT_AT=0.9 python -I t11_units.py ${P}11k 52 0 2100:1336,2100:6692 2100:6692 2100:4966
run ${P}20 python -I t20_cross.py ${P}20
run ${P}6 python -I t5_fidelity.py ${P}6 30 18 1.6
echo "##### done ($(date +%H:%M:%S))"
