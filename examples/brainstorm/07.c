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
  size_t n = fread(a, 1, sizeof(a), fp);
  printf("read %zu bytes\n", n);
  fclose(fp);
  if (!memcmp(a, "hello-world", 11)) {
    printf("OK\n");
  }
  if (!memcmp(a, "goodbye-earth", 13)) {
    printf("Also OK\n");
  }
  return 0;
}

// command:
// ./build/bin/klee --libc=uclibc --posix-runtime 07.bc
// output:
// KLEE: done: total instructions = 14115
// KLEE: done: completed paths = 1
// KLEE: done: partially completed paths = 0
// KLEE: done: generated tests = 1

// command:
// ./build/bin/klee --libc=uclibc --posix-runtime 07.bc A -sym-files 1 40
// output:
// read 40 bytes
// read 40 bytes
// KLEE: done: total instructions = 27633
// KLEE: done: completed paths = 50
// KLEE: done: partially completed paths = 0
// KLEE: done: generated tests = 50
