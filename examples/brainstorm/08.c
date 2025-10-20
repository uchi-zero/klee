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

// command:
// ./build/bin/klee --libc=uclibc --posix-runtime 08.bc A -sym-files 1 40
// output:
// read 40 bytes
// read 40 bytes
// KLEE: done: total instructions = 22024
// KLEE: done: completed paths = 6
// KLEE: done: partially completed paths = 0
// KLEE: done: generated tests = 6
