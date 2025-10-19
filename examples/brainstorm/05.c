#include "klee/klee.h"
#include <stdio.h>
#include <string.h>

int main() {
  for (int i = 0; i < 3; i++) {
    char a[40];
    klee_make_symbolic(a, sizeof(a), "a");
    if (memcmp(a, "hello-world", 11) == 0) {
      printf("OK\n");
    }
    if (memcmp(a, "goodbye-earth", 13) != 0) {
      printf("Also OK\n");
    }
  }
  return 0;
}

// output:
// KLEE: done: total instructions = 2173947
// KLEE: done: completed paths = 15625
// KLEE: done: partially completed paths = 0
// KLEE: done: generated tests = 15625
