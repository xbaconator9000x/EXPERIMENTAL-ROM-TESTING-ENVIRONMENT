#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build evidence
cc -std=c11 -O2 -Wall -Wextra core/state_runner.c -o build/state_runner -lmgba
python3 -m unittest discover -s tests -v
python3 tests/make_gba_fixture.py --output build/synthetic.gba
sha="$(sha256sum build/synthetic.gba | cut -d' ' -f1)"
python3 core/run_locked.py --runner build/state_runner --rom build/synthetic.gba --sha256 "$sha" --scenario tests/scenarios/input-pass.txt --out evidence/pass | tee evidence/pass.log
grep -q 'RESULT PASS.*checks=4' evidence/pass.log
for item in timeout-fail:5 assert-fail:5 no-assert-fail:2 invalid-fail:2; do
  name="${item%:*}"
  expected="${item#*:}"
  set +e
  build/state_runner build/synthetic.gba "tests/scenarios/$name.txt" "evidence/$name" > "evidence/$name.log" 2>&1
  code=$?
  set -e
  test "$code" -eq "$expected"
  grep -q 'RESULT FAIL' "evidence/$name.log"
done
if python3 core/run_locked.py --runner build/state_runner --rom build/synthetic.gba --sha256 "$(printf '%064d' 0)" --scenario tests/scenarios/input-pass.txt --out evidence/wrong; then
  echo 'Wrong hash unexpectedly accepted'; exit 1
fi
echo 'PASS: synthetic native input and assertion regressions, not actual game acceptance'

cc -std=c11 -O2 -Wall -Wextra core/live_runner.c -o build/live_runner -lmgba
clang --target=arm-none-eabi -mcpu=arm7tdmi -fuse-ld=lld -nostdlib -Wl,-Ttext=0x080000c0,--oformat=binary tests/field_fixture.s -o build/field.bin
python3 tests/native_walk.py | tee evidence/native-walk.log
