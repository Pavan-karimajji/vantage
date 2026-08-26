# WP-34 (SM-11): vantage's real windowed main() -- links vantage_bridge
# (the engine/tick mechanism, WP-33) and AdasViz::runner (the extracted
# window/render-loop body, modules/viz's own WP-34 half). No GLFW/ImGui
# link line here: vantage_app.cpp never includes those headers itself
# (player_runner.hpp's own top note has the full account of why), and
# AdasViz::runner already carries their archives. OpenGL is the one
# exception -- a system library, never Conan-packaged (viz's own conf/
# build.yml `toolkit` component's own comment: "a consumer still needs its
# own find_package(OpenGL REQUIRED) + OpenGL::GL"), found live here the
# same way: `adas-viz-runner.lib(player_runner.obj)` left __imp_glClear/
# __imp_glClearColor/__imp_glViewport unresolved until this find_package()
# was added.
find_package(OpenGL REQUIRED)
add_executable(vantage_app vantage_app.cpp)
target_link_libraries(vantage_app PRIVATE AdasVantage::AdasVantage AdasViz::runner OpenGL::GL)
