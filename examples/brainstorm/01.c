#include "klee/klee.h"
#include <stdio.h>
#include <string.h>

int main() {
  char a[40];
  klee_make_symbolic(a, sizeof(a), "a");
  if (!memcmp(a, "hello-world", 11)) {
    printf("OK\n");
  }
  return 0;
}

// output:
// KLEE: done: total instructions = 13863
// KLEE: done: completed paths = 12
// KLEE: done: partially completed paths = 0
// KLEE: done: generated tests = 12
