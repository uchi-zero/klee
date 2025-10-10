#include "lauxlib.h"
#include "lua.h"
#include "lualib.h"
#include <klee/klee.h>

int main() {
  char symbolic_content[40];
  klee_make_symbolic(symbolic_content, sizeof(symbolic_content), "content");

  klee_assume(symbolic_content[0] != '#');
  for (int i = 0; i < 40; i++) {
    klee_assume(symbolic_content[i] != '\0');
  }

  lua_State *L = luaL_newstate();
  luaL_openlibs(L);

  int status = luaL_loadbuffer(L, symbolic_content, 40, "symbolic_chunk");

  if (status == LUA_OK) {
    lua_pcall(L, 0, 0, 0);
  }

  lua_close(L);
  return 0;
}
