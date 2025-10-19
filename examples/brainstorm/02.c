#include "klee/klee.h"
#include <stdio.h>
#include <string.h>

int main() {
  char a[40];
  klee_make_symbolic(a, sizeof(a), "a");
  int bid = klee_range(
      0, 2, "bid"); // klee_choose need to manually check all possible values
  klee_open_merge();
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
  return 0;
}

// output:
// KLEE: done: total instructions = 12977
// KLEE: done: completed paths = 12
// KLEE: done: partially completed paths = 0
// KLEE: done: generated tests = 12
