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
    if (!memcmp(a, "hello-world", 11)) {
      printf("OK\n");
    }
    if (!memcmp(a, "goodbye-earth", 13)) {
      printf("Also OK\n");
    }
  }
  if (!memcmp(a, "space", 5)) {
    printf("That's the end\n");
  }
  return 0;
}

// command:
// ./build/bin/klee --libc=uclibc --posix-runtime
// --only-output-states-covering-new --max-time=30s 09.bc A -sym-files 1 40
// output:
// KLEE: done: total instructions = 8315050
// KLEE: done: completed paths = 0
// KLEE: done: partially completed paths = 112507
// KLEE: done: generated tests = 4
// comments:
// 30s: no "OK" or "Also OK" output
// 15min: "OK" outputs
