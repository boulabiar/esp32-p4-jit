idf_component_register(SRCS "app_main.cpp" "app_wrapper.cpp"
                       INCLUDE_DIRS "."
                       REQUIRES esp-dl p4_jit nvs_flash)

# Force the linker to include these JIT-called symbols
target_link_libraries(${COMPONENT_LIB} PRIVATE 
    "-Wl,--undefined=app_model_init_from_ram"
    "-Wl,--undefined=app_preprocess_from_buffer"
    "-Wl,--undefined=app_model_run"
    "-Wl,--undefined=app_get_score"
)
