# WP-14 (VANTAGE, C2): the live measurement writer library, before simcore, which links it.
add_subdirectory(livemeas)
# WP-03: simcore has real content now (errors/events.cpp).
add_subdirectory(simcore)
# WP-14 (SI-09): simengine -- the thin executable, now that main.cpp exists.
add_subdirectory(simengine)
# WP-16 (VANTAGE, C2): vantage-inspect -- the live measurement inspector.
add_subdirectory(inspector)
