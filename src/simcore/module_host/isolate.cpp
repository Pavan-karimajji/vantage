// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `RunIsolatedStage` (`IMP-0096`, `WP-14`): spawns a child process,
///   waits up to a deadline, and classifies what happened to it --
///   `fail`/`crash`/`timeout` (`R-SIM-19`, ported in spirit from
///   `adas_sim/orchestrate/batch.py::_classify`'s own three-way split,
///   the one existing, working twin of this decision in this codebase).
///   `batch.py` tells `crash` from `fail` by whether the child left behind
///   a self-reported outcome file; this host-side primitive has no such
///   sidecar to read, so it draws the same line the platform itself
///   already draws: a clean exit (any code) is `fail` when nonzero, and an
///   ABNORMAL termination -- a POSIX signal, or a Windows
///   unhandled-exception-style exit status -- is `crash`. Both still never
///   merge with `timeout`, which this function detects itself rather than
///   inferring from the exit status at all.
/// @author Pavan Karimajji

#include "simcore/module_host.hpp"

#include <array>
#include <chrono>
#include <thread>

#if defined(_WIN32)
#include <windows.h>
#else
#include <fcntl.h>
#include <spawn.h>
#include <sys/wait.h>
#include <unistd.h>
extern char** environ;
#endif

namespace simcore::module_host {

std::string ToString(IsolatedOutcome outcome) {
  switch (outcome) {
    case IsolatedOutcome::kOk:
      return "ok";
    case IsolatedOutcome::kFail:
      return "fail";
    case IsolatedOutcome::kCrashed:
      return "crash";
    case IsolatedOutcome::kTimedOut:
      return "timeout";
    case IsolatedOutcome::kFailedToStart:
      return "failed_to_start";
  }
  return "failed_to_start";  // unreachable for a valid value
}

#if defined(_WIN32)

IsolatedRunResult RunIsolatedStage(const std::string& stage, const std::filesystem::path& executable,
                                    const std::vector<std::string>& args, std::chrono::milliseconds timeout,
                                    const std::filesystem::path& stderr_capture_path) {
  IsolatedRunResult result;
  result.stage = stage;

  std::string cmd = "\"" + executable.string() + "\"";
  for (const std::string& arg : args) {
    cmd += " \"" + arg + "\"";
  }

  STARTUPINFOA startup_info{};
  startup_info.cb = sizeof(startup_info);
  PROCESS_INFORMATION process_info{};
  std::vector<char> cmd_buf(cmd.begin(), cmd.end());
  cmd_buf.push_back('\0');

  // WP-15 (SW-0139): redirect the child's stderr to a capture file rather
  // than inheriting the parent's -- opt-in only (`stderr_capture_path`
  // empty preserves every existing caller's exact prior behaviour).
  HANDLE stderr_file = INVALID_HANDLE_VALUE;
  if (!stderr_capture_path.empty()) {
    SECURITY_ATTRIBUTES sa{};
    sa.nLength = sizeof(sa);
    sa.bInheritHandle = TRUE;
    stderr_file = CreateFileA(stderr_capture_path.string().c_str(), GENERIC_WRITE, FILE_SHARE_READ, &sa,
                               CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (stderr_file != INVALID_HANDLE_VALUE) {
      startup_info.dwFlags |= STARTF_USESTDHANDLES;
      startup_info.hStdError = stderr_file;
      startup_info.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
      startup_info.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    }
  }

  const BOOL spawned = CreateProcessA(nullptr, cmd_buf.data(), nullptr, nullptr,
                                       stderr_file != INVALID_HANDLE_VALUE ? TRUE : FALSE, 0, nullptr, nullptr,
                                       &startup_info, &process_info);
  if (stderr_file != INVALID_HANDLE_VALUE) CloseHandle(stderr_file);
  if (!spawned) {
    result.outcome = IsolatedOutcome::kFailedToStart;
    result.detail = "CreateProcessA failed, GetLastError=" + std::to_string(GetLastError());
    return result;
  }
  CloseHandle(process_info.hThread);

  const DWORD wait_result = WaitForSingleObject(process_info.hProcess, static_cast<DWORD>(timeout.count()));
  if (wait_result == WAIT_TIMEOUT) {
    TerminateProcess(process_info.hProcess, 1);
    WaitForSingleObject(process_info.hProcess, INFINITE);
    CloseHandle(process_info.hProcess);
    result.outcome = IsolatedOutcome::kTimedOut;
    return result;
  }

  DWORD exit_code = 0;
  GetExitCodeProcess(process_info.hProcess, &exit_code);
  CloseHandle(process_info.hProcess);
  result.exit_code = static_cast<int>(exit_code);
  // An NTSTATUS-shaped exit code (top bit set, e.g. STATUS_ACCESS_VIOLATION
  // 0xC0000005) is the closest cross-platform-honest signal of "the process
  // never got to report" -- the same abnormal-termination line POSIX draws
  // with WIFSIGNALED below.
  if ((exit_code & 0x80000000u) != 0) {
    result.outcome = IsolatedOutcome::kCrashed;
  } else if (exit_code == 0) {
    result.outcome = IsolatedOutcome::kOk;
  } else {
    result.outcome = IsolatedOutcome::kFail;
  }
  return result;
}

#else

IsolatedRunResult RunIsolatedStage(const std::string& stage, const std::filesystem::path& executable,
                                    const std::vector<std::string>& args, std::chrono::milliseconds timeout,
                                    const std::filesystem::path& stderr_capture_path) {
  IsolatedRunResult result;
  result.stage = stage;

  std::vector<std::string> argv_storage;
  argv_storage.push_back(executable.string());
  argv_storage.insert(argv_storage.end(), args.begin(), args.end());
  std::vector<char*> argv;
  argv.reserve(argv_storage.size() + 1);
  for (std::string& s : argv_storage) argv.push_back(s.data());
  argv.push_back(nullptr);

  // WP-15 (SW-0139): redirect fd 2 (stderr) to a capture file, opt-in only
  // -- an empty `stderr_capture_path` runs `posix_spawn_file_actions_init`
  // with no `adddup2`, which is exactly `posix_spawn`'s own inherited-fd
  // default (no behaviour change for any existing caller).
  posix_spawn_file_actions_t file_actions;
  posix_spawn_file_actions_init(&file_actions);
  const bool capture_stderr = !stderr_capture_path.empty();
  if (capture_stderr) {
    posix_spawn_file_actions_addopen(&file_actions, 2, stderr_capture_path.c_str(),
                                      O_WRONLY | O_CREAT | O_TRUNC, 0644);
  }

  pid_t pid = 0;
  const int spawn_status =
      posix_spawn(&pid, executable.c_str(), &file_actions, nullptr, argv.data(), environ);
  posix_spawn_file_actions_destroy(&file_actions);
  if (spawn_status != 0) {
    result.outcome = IsolatedOutcome::kFailedToStart;
    result.detail = "posix_spawn failed, errno=" + std::to_string(spawn_status);
    return result;
  }

  const auto deadline = std::chrono::steady_clock::now() + timeout;
  int status = 0;
  for (;;) {
    const pid_t waited = waitpid(pid, &status, WNOHANG);
    if (waited == pid) break;
    if (std::chrono::steady_clock::now() >= deadline) {
      kill(pid, SIGKILL);
      waitpid(pid, &status, 0);  // reap -- never leave a zombie behind
      result.outcome = IsolatedOutcome::kTimedOut;
      return result;
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }

  if (WIFSIGNALED(status)) {
    result.outcome = IsolatedOutcome::kCrashed;
    result.exit_code = WTERMSIG(status);
    result.detail = "terminated by signal " + std::to_string(WTERMSIG(status));
  } else if (WIFEXITED(status)) {
    result.exit_code = WEXITSTATUS(status);
    result.outcome = result.exit_code == 0 ? IsolatedOutcome::kOk : IsolatedOutcome::kFail;
  } else {
    result.outcome = IsolatedOutcome::kCrashed;
    result.detail = "child terminated abnormally, raw status=" + std::to_string(status);
  }
  return result;
}

#endif

}  // namespace simcore::module_host
