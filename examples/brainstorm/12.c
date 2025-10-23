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
  char file_content[40];
  fread(file_content, 1, 40, fp);

  char a[40];
  int total_len = 0;
  while (while_cond()) {
    klee_assert(total_len <= 40);
    klee_make_symbolic(&a, 40, "line");
    int str_len = klee_range(0, 40, "str_len");
    klee_assume(a[str_len] == '\0');
    total_len += str_len + 1;
    if (!memcmp(a, "hello-world", 11)) {
      printf("OK\n");
    }
    if (!memcmp(a, "goodbye-earth", 13)) {
      printf("Also OK\n");
    }
    for (int j = total_len; j < total_len + str_len + 1; j++) { // this spend too much time?
        klee_assume(file_content[j] == a[j]);
      }
  }
  if (!memcmp(a, "space", 5)) {
    printf("That's the end\n");
  }
  return 0;
}
