#include <klee/klee.h>
#include <stdio.h>
#include <string.h>

int while_cond() { return klee_range(0, 2, "while_condition"); }

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
  int total_len = 0;
  while (while_cond()) {
    klee_assert(total_len <= 40);
    klee_make_symbolic(&a, 40, "a");
    int str_len = klee_range(0, 40, "str_len");
    klee_assume(a[str_len] == '\0');
    total_len += str_len + 1;
    printf("OK");
  }
  return 0;
}

// command:
// ./build/bin/klee --libc=uclibc --posix-runtime
// --only-output-states-covering-new --max-time=10s 14.bc A -sym-files 1 40
// output:
// KLEE: done: total instructions = 35331
// KLEE: done: completed paths = 84
// KLEE: done: partially completed paths = 80
// KLEE: done: generated tests = 2
// comments:
// 10s: "OK" output not so many times