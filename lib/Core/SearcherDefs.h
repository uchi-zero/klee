//===-- SearcherDefs.h ------------------------------------------*- C++ -*-===//
//
//                     The KLEE Symbolic Virtual Machine
//  Empc: Effective Path Prioritization for Symbolic Execution with Path Cover
//
// This file is distributed under the University of Illinois Open Source
// License. See LICENSE.TXT for details.
//
// Copyright (c) 2024-2025 Shuangjie (Joshua) Yao.
// All rights reserved.
//
//===----------------------------------------------------------------------===//

#ifndef SEARCHERDEFS_HPP_
#define SEARCHERDEFS_HPP_

#include <deque>
#include <map>

namespace klee {

/// [SGS]:
typedef std::deque<std::pair<unsigned, unsigned>> subpath_ty;

/// [SGS]:
typedef std::map<subpath_ty, unsigned long> subpathCount_ty;

namespace Empc {
enum class StateStepType {
  COMMON,
  PUSH,
  POP,
};

}
} // namespace klee

#endif