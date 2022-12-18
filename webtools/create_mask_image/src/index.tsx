import Cropper from "cropperjs"
import React, { useRef, useState } from "react"
import { createRoot } from "react-dom/client"
import ReactCrop, { Crop } from "react-image-crop"
import "react-image-crop/dist/ReactCrop.css"
import { observable } from "mobx"
import { observer } from "mobx-react"
import { AppState } from "./states/app"
import { Save } from "./components/header/save"

const APP_DIV = document.getElementById("app")!

function assignCallback<T extends Crop, K extends keyof T>(key: K, value: T[K]) {
    return <TA extends T | undefined | null>(input: TA) => {
        if (input == null) return input
        return {
            ...input,
            [key]: value,
        }
    }
}
function assignCallbackFunc<T extends Crop, K extends keyof T>(key: K, value: ((input: T) => T[K])) {
    return <TA extends T | undefined | null>(input: TA) => {
        if (input == null) return input
        return {
            ...input,
            [key]: value(input),
        }
    }
}

const App = observer(({appState}: {appState: AppState}) => {
    const [currentImg, setCurrentImg] = useState<string>()
    return <div>
        <div id="headerbar">
            <Save appState={appState} />
            <fieldset>
                <legend>Crop</legend>
                <table>
                    <tr>
                        <td>
                            X: <input type="number" value={appState.crop?.x} onInput={e => appState.updateCropPartially("x", e.currentTarget.valueAsNumber)} />
                            <button onClick={e => appState.updateCropPartially("x", crop => (1920-crop.width)/2)}>C</button>
                            <button onClick={e => appState.updateCropPartially("x", crop => Math.floor(crop.x/8)*8)}>o8</button>
                        </td>
                        <td>
                            Y: <input type="number" value={appState.crop?.y} onInput={e => appState.updateCropPartially("y", e.currentTarget.valueAsNumber)} />
                            <button onClick={e => appState.updateCropPartially("y", crop => (1080-crop.height)/2)}>C</button>
                            <button onClick={e => appState.updateCropPartially("y", crop => Math.floor(crop.y/8)*8)}>o8</button>
                        </td>
                    </tr>
                    <tr>
                        <td>
                            W: <input type="number" value={appState.crop?.width} onInput={e => appState.updateCropPartially("width", e.currentTarget.valueAsNumber)} />
                            <button onClick={e => appState.updateCropPartially("width", crop => Math.floor(crop.width/8)*8)}>o8</button>
                        </td>
                        <td>
                            H: <input type="number" value={appState.crop?.height} onInput={e => appState.updateCropPartially("height", e.currentTarget.valueAsNumber)} />
                            <button onClick={e => appState.updateCropPartially("height", crop => Math.floor(crop.height/8)*8)}>o8</button>
                        </td>
                    </tr>
                </table>
            </fieldset>
        </div>
        <div style={{width: 1920, height: 1080}} onDrop={e => {
            e.stopPropagation()
            e.preventDefault()
            const file = e.dataTransfer.files[0]
            setCurrentImg(current => {
                if (current != null) URL.revokeObjectURL(current)
                return URL.createObjectURL(file)
            })
        }} onDragOver={e => {
            e.preventDefault()
            e.stopPropagation()
        }}>
            <ReactCrop crop={appState.crop} onChange={c => appState.updateCrop(c)}>
                <img ref={i => appState.image = i} src={currentImg} />
            </ReactCrop>
        </div>
    </div>
})

createRoot(APP_DIV).render(<App appState={new AppState()} />)