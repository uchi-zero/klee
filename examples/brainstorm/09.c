#include "klee/klee.h"
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv) {
  if (argc < 2) {
    fprintf(stderr, "usage: %s <input-file>\n", argv[0]);
    return 1;
  }
  FILE *fp = fopen(argv[1], "r");
  if (!fp) {
    perror("fopen");
    return 1;
  }
  char a[40];
  while (fgets(a, sizeof(a), fp) != NULL) {
    if (memcmp(a, "hello-world", 11) == 0) {
      printf("OK\n");
    }
    if (memcmp(a, "goodbye-earth", 13) != 0) {
      printf("Also OK\n");
    }
  }
  return 0;
}

// command:
// ./build/bin/klee --libc=uclibc --posix-runtime --max-time=30s 09.bc A
// -sym-files 1 40
// output:
// KLEE: done: total instructions = 7519530
// KLEE: done: completed paths = 0
// KLEE: done: partially completed paths = 100782
// KLEE: done: generated tests = 100782
