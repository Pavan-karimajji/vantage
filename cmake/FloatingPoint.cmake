# IMP-0365 - the required floating-point flags, set once and applied to
# every simcore/simengine target via adas_sim_apply_fp_flags(). Determinism
# (R-SIM-24) needs the compiler to never reorder or contract floating-point
# expressions: /fp:precise (MSVC) is precise-but-not-strict (no exception
# semantics needed here, just no reassociation); -ffp-contract=off (GCC/
# Clang) disables fused-multiply-add contraction, which /fp:precise already
# implies on MSVC.
include_guard(GLOBAL)

function(adas_sim_apply_fp_flags target)
    if(MSVC)
        target_compile_options(${target} PRIVATE /fp:precise)
    else()
        target_compile_options(${target} PRIVATE -ffp-contract=off)
    endif()
endfunction()
