import pluginTypescript from "@rollup/plugin-typescript"
import pluginNodeResolve from "@rollup/plugin-node-resolve"
import pluginCommonjs from "@rollup/plugin-commonjs"
import pluginReplace from "@rollup/plugin-replace"
import pluginImportCss from "rollup-plugin-import-css"

/** @type {import("rollup").RollupOptions} */
const config = [{
    input: "create_mask_image/src/index.tsx",
    output: {
        file: "create_mask_image/index.js",
        format: "esm",
    },
    plugins: [
        pluginTypescript(),
        pluginNodeResolve({browser: true}),
        pluginCommonjs(),
        pluginReplace({
            "process.env.NODE_ENV": JSON.stringify("development")
        }),
        pluginImportCss(),
    ]
}]

export default config