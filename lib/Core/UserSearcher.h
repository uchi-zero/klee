//===-- UserSearcher.h ------------------------------------------*- C++ -*-===//
//
//                     The KLEE Symbolic Virtual Machine
//
// This file is distributed under the University of Illinois Open Source
// License. See LICENSE.TXT for details.
//
//===----------------------------------------------------------------------===//

#ifndef KLEE_USERSEARCHER_H
#define KLEE_USERSEARCHER_H

namespace klee {
class Executor;
class Searcher;

// XXX gross, should be on demand?
bool userSearcherRequiresMD2U();
bool userSearcherRequiresInMemoryExecutionTree();

/// @brief [Empc]: The searcher is `EmpcSearcher` so it requires searcher graphs
/// @return
bool userSearcherRequiresSearcherGraph();

/// @brief [SGS]: Requires SGS
/// @return
bool userSearcherRequiresSGS();

void initializeSearchOptions();

Searcher *constructUserSearcher(Executor &executor);
} // namespace klee

#endif /* KLEE_USERSEARCHER_H */
