import { action, makeObservable, observable } from "mobx"
import { Crop } from "react-image-crop"

export class AppState {
    @observable dir?: FileSystemDirectoryHandle
    @observable localeDirs: FileSystemDirectoryHandle[] = []
    @observable name: string = ""
    @observable image: HTMLImageElement | null = null
    @observable crop?: Crop
    @observable currentLocaleDir?: FileSystemDirectoryHandle

    constructor() {
        makeObservable(this)
    }

    @action setDir(dir: FileSystemDirectoryHandle) {
        this.dir = dir
        this.reloadLocaleDirs()
    }

    async reloadLocaleDirs() {
        if (this.dir == null) return
        const localeDirs = []
        for await (const entry of this.dir.values()) {
            if (entry.kind === "directory") {
                localeDirs.push(entry)
            }
        }
        this.updateLocaleDirs(localeDirs)
    }

    @action updateLocaleDirs(localeDirs: FileSystemDirectoryHandle[]) {
        this.currentLocaleDir = undefined
        this.localeDirs = localeDirs
    }

    @action updateCrop(crop: Crop) {
        this.crop = crop
    }

    @action updateCropPartially(key: "x" | "y" | "width" | "height", value: number | ((prev: Crop) => number)) {
        if (this.crop == null) return
        this.crop![key] = typeof value === "function" ? value(this.crop) : value
    }

    async save() {
        const { currentLocaleDir, name, crop } = this
        if (currentLocaleDir == null) {
            alert("Please select a locale")
            return
        }
        if (name === "") {
            alert("Please enter a name")
            return
        }
        if (crop == null) {
            alert("Please crop the image")
            return
        }
        const canvas = document.createElement("canvas")
        canvas.width = crop.width
        canvas.height = crop.height
        const ctx = canvas.getContext("2d")
        if (ctx == null) {
            alert("Please crop the image")
            return
        }
        ctx.drawImage(this.image!, crop.x, crop.y, crop.width, crop.height, 0, 0, crop.width, crop.height)
        // grayscale 0xE0 threshold
        const imageData = ctx.getImageData(0, 0, crop.width, crop.height)
        const data = imageData.data
        for (let i = 0; i < data.length; i += 4) {
            const r = data[i]
            const g = data[i + 1]
            const b = data[i + 2]
            const a = data[i + 3]
            const gray = (r + g + b) / 3
            for (let j = 0; j < 3; j++) {
                data[i + j] = gray > 0xE0 ? 0xFF : 0x00
            }
        }
        ctx.putImageData(imageData, 0, 0)
        const pngURL = canvas.toDataURL("image/png")
        const pngBase64 = pngURL.slice(pngURL.indexOf(",") + 1)
        const pngBinary = atob(pngBase64)
        const pngBuffer = new Uint8Array(pngBinary.length)
        for (let i = 0; i < pngBinary.length; i++) {
            pngBuffer[i] = pngBinary.charCodeAt(i)
        }
        const pngFile = new File([pngBuffer], `${this.name}.png`, { type: "image/png" })
        const pngHandle = await currentLocaleDir.getFileHandle(`${this.name}.png`, { create: true })
        const pngWritable = await pngHandle.createWritable()
        await pngWritable.write(pngBuffer)
        await pngWritable.close()
        const json = {
            x: crop.x,
            y: crop.y,
        }
        const jsonFile = new File([JSON.stringify(json)], `${this.name}.json`, { type: "application/json" })
        const jsonHandle = await currentLocaleDir.getFileHandle(`${this.name}.json`, { create: true })
        const jsonWritable = await jsonHandle.createWritable()
        await jsonWritable.write(JSON.stringify(json))
        await jsonWritable.close()
        alert("Saved")
    }
}