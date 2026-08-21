// Copyright (c) <ORG>. All Rights Reserved.
// Proprietary and Confidential.
// COMPONENT: SIM
/// @file
/// @brief
///   `Dso` implementation -- ported from `sil_host/src/library_loader.cpp`
///   (`ResolveLibrary` + `DynamicLibrary`), folded into one `Open` call
///   (`IMP-0079`'s `DEDUPE`).
/// @author Pavan Karimajji

#include "simcore/module_host.hpp"

#if defined(_WIN32)
#include <windows.h>
#else
#include <dlfcn.h>
#endif

#include <sstream>

namespace simcore::module_host {

namespace {

// Mirrors `library_loader.cpp::CandidateNames` exactly: one Windows name,
// two Linux names (lib-prefixed tried before bare, same order).
std::vector<std::string> CandidateNames(const std::string& stem) {
#if defined(_WIN32)
  return {stem + ".dll"};
#else
  return {"lib" + stem + ".so", stem + ".so"};
#endif
}

std::string JoinPaths(const std::vector<std::filesystem::path>& paths) {
  if (paths.empty()) {
    return "(no directories given)";
  }
  std::ostringstream out;
  for (std::size_t i = 0; i < paths.size(); ++i) {
    if (i != 0) {
      out << ", ";
    }
    out << paths[i].string();
  }
  return out.str();
}

std::string JoinNames(const std::vector<std::string>& names) {
  std::ostringstream out;
  for (std::size_t i = 0; i < names.size(); ++i) {
    if (i != 0) {
      out << ", ";
    }
    out << names[i];
  }
  return out.str();
}

void* PlatformLoad(const std::filesystem::path& path, std::string& load_error) {
#if defined(_WIN32)
  void* handle = static_cast<void*>(LoadLibraryW(path.wstring().c_str()));
  if (handle == nullptr) {
    load_error = "LoadLibraryW failed, GetLastError=" + std::to_string(GetLastError());
  }
  return handle;
#else
  void* handle = dlopen(path.string().c_str(), RTLD_NOW | RTLD_LOCAL);
  if (handle == nullptr) {
    const char* err = dlerror();
    load_error = err != nullptr ? err : "dlopen failed";
  }
  return handle;
#endif
}

void PlatformUnload(void* handle) {
  if (handle == nullptr) {
    return;
  }
#if defined(_WIN32)
  FreeLibrary(static_cast<HMODULE>(handle));
#else
  dlclose(handle);
#endif
}

}  // namespace

Dso::Dso(std::filesystem::path path, void* handle) : path_(std::move(path)), handle_(handle) {}

Dso::Dso(Dso&& other) noexcept : path_(std::move(other.path_)), handle_(other.handle_) {
  other.handle_ = nullptr;
}

Dso& Dso::operator=(Dso&& other) noexcept {
  if (this != &other) {
    PlatformUnload(handle_);
    path_ = std::move(other.path_);
    handle_ = other.handle_;
    other.handle_ = nullptr;
  }
  return *this;
}

Dso::~Dso() {
  PlatformUnload(handle_);
}

Result<Dso> Dso::Open(const std::string& stem, const std::vector<std::filesystem::path>& search_dirs) {
  const std::vector<std::string> candidates = CandidateNames(stem);
  std::filesystem::path resolved;
  bool found = false;
  for (const auto& dir : search_dirs) {
    for (const auto& name : candidates) {
      std::error_code ec;
      std::filesystem::path candidate_path = dir / name;
      if (std::filesystem::is_regular_file(candidate_path, ec)) {
        resolved = candidate_path;
        found = true;
        break;
      }
    }
    if (found) {
      break;
    }
  }
  if (!found) {
    return Result<Dso>::Fail(Error{Kind::Environment, "stem '" + stem + "' as one of: " + JoinNames(candidates),
                                    "none of those files exist", "search directories: " + JoinPaths(search_dirs),
                                    "build the component, or add its output directory to the search path"});
  }

  std::string load_error;
  void* handle = PlatformLoad(resolved, load_error);
  if (handle == nullptr) {
    return Result<Dso>::Fail(Error{Kind::Environment, "a loadable library implementing the generic SIL ABI",
                                    load_error, resolved.string(),
                                    "check the library was built for this platform and its dependencies are "
                                    "resolvable"});
  }
  return Result<Dso>::Ok(Dso(resolved, handle));
}

Result<Dso> Dso::OpenPath(const std::filesystem::path& path) {
  std::error_code ec;
  if (!std::filesystem::is_regular_file(path, ec)) {
    return Result<Dso>::Fail(Error{Kind::Environment, "a loadable library implementing the generic SIL ABI",
                                    "no such file", path.string(), "check the path is correct and the library was built"});
  }
  std::string load_error;
  void* handle = PlatformLoad(path, load_error);
  if (handle == nullptr) {
    return Result<Dso>::Fail(Error{Kind::Environment, "a loadable library implementing the generic SIL ABI",
                                    load_error, path.string(),
                                    "check the library was built for this platform and its dependencies are "
                                    "resolvable"});
  }
  return Result<Dso>::Ok(Dso(path, handle));
}

void Dso::Leak() {
  handle_ = nullptr;
}

void* Dso::Symbol(const std::string& name) const {
#if defined(_WIN32)
  return reinterpret_cast<void*>(GetProcAddress(static_cast<HMODULE>(handle_), name.c_str()));
#else
  return dlsym(handle_, name.c_str());
#endif
}

}  // namespace simcore::module_host
