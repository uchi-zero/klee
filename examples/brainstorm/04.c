#include "klee/klee.h"
#include <stdio.h>
#include <string.h>

int main() {
  char a[40];
  klee_make_symbolic(a, sizeof(a), "a");
  int bid = klee_range(0, 3, "bid");
  if (bid == 0) {
    klee_assume(a[0] == 'h');
    klee_assume(a[1] == 'e');
    klee_assume(a[2] == 'l');
    klee_assume(a[3] == 'l');
    klee_assume(a[4] == 'o');
    klee_assume(a[5] == '-');
    klee_assume(a[6] == 'w');
    klee_assume(a[7] == 'o');
    klee_assume(a[8] == 'r');
    klee_assume(a[9] == 'l');
    klee_assume(a[10] == 'd');
    printf("OK\n");
  }
  if (bid == 1) {
    klee_assume(a[0] == 'g');
    klee_assume(a[1] == 'o');
    klee_assume(a[2] == 'o');
    klee_assume(a[3] == 'd');
    klee_assume(a[4] == 'b');
    klee_assume(a[5] == 'y');
    klee_assume(a[6] == 'e');
    klee_assume(a[7] == '-');
    klee_assume(a[8] == 'e');
    klee_assume(a[9] == 'a');
    klee_assume(a[10] == 'r');
    klee_assume(a[11] == 't');
    klee_assume(a[12] == 'h');
    printf("Also OK\n");
  }
  return 0;
}

// output:
// KLEE: done: total instructions = 13003
// KLEE: done: completed paths = 25
// KLEE: done: partially completed paths = 0
// KLEE: done: generated tests = 25
