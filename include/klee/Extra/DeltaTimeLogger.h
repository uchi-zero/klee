//===-- DeltaTimeDumper.h ----------------------------------*- C++ -*-===//
//
//                     The KLEE Symbolic Virtual Machine
//
// This file is distributed under the University of Illinois Open Source
// License. See LICENSE.TXT for details.
//
//===----------------------------------------------------------------------===//

#ifndef KLEE_DELTATIMELOGGER_H
#define KLEE_DELTATIMELOGGER_H

#include "klee/Statistics/Statistics.h"
#include "klee/Support/Timer.h"

#include <string>
#include <iostream>
#include <fstream>
#include <chrono>

namespace klee {

/**
 * A DeltaTimeDumper dumps the delta time to a specified file.
 */
class DeltaTimeLogger {
private:
  const WallTimer timer;
  std::string filePath;

public:
  explicit DeltaTimeLogger(std::string filePath) : filePath(std::move(filePath)) {}
  ~DeltaTimeLogger(){}

  void lap(std::string status) {
    auto delta = timer.delta().toMicroseconds();
    std::ofstream file(this->filePath, std::ios::app);
    if (!file)
        return;
    auto now = std::chrono::system_clock::now();
    std::time_t now_time = std::chrono::system_clock::to_time_t(now);
    file << now_time << "," << status << "," << delta << "\n";
  }
};
} // namespace klee

#endif /* KLEE_DELTATIMEDUMPER_H */
