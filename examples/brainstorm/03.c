#include "klee/klee.h"
#include <stdio.h>
#include <string.h>

int main() {
  char a[40];
  klee_make_symbolic(a, sizeof(a), "a");
  if (!memcmp(a, "hello-world", 11)) {
    printf("OK\n");
  }
  if (!memcmp(a, "goodbye-earth", 13)) {
    printf("Also OK\n");
  }
  return 0;
}

// output:
// KLEE: done: total instructions = 15765
// KLEE: done: completed paths = 25
// KLEE: done: partially completed paths = 0
// KLEE: done: generated tests = 25
