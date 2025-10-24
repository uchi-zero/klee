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
  while (fgets(a, sizeof(a), fp) != NULL) { // how many times will this loop run?
    printf("OK");
  }
  return 0;
}

// command:
// ./build/bin/klee --libc=uclibc --posix-runtime
// --only-output-states-covering-new --max-time=10s 13.bc A -sym-files 1 40
// output:
// KLEE: done: total instructions = 2871145
// KLEE: done: completed paths = 0
// KLEE: done: partially completed paths = 46384
// KLEE: done: generated tests = 4
// comments:
// 10s: "OK" output so many times