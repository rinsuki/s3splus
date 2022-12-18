import React from "react"
import { observer } from "mobx-react";
import { AppState } from "../../states/app";

export const Save = observer(({appState}: {appState: AppState}) => {
    return <fieldset id="save">
        <legend>Save</legend>
        {
            appState.dir == null && 
            <button onClick={() => window.showDirectoryPicker({id: "s3s-masks-folder", mode: "readwrite"}).then(d => appState.setDir(d))}>mount masks/ folder</button>
        }
        {
            appState.dir != null && 
            <form style={{display: "inline-block"}} onSubmit={e => {
                e.preventDefault()
                appState.save()
            }}>
                <table>
                    <tr>
                        <td>Locale:</td>
                        <td>
                            <select value={appState.currentLocaleDir?.name} onChange={e => {
                                appState.currentLocaleDir = appState.localeDirs.find(ld => ld.name === e.currentTarget.value)
                            }}>
                                <option></option>
                                {...appState.localeDirs.map(ld => {
                                    return <option key={ld.name} value={ld.name}>{ld.name}</option>
                                })}
                            </select>
                            <button type="button" onClick={() => appState.reloadLocaleDirs()}>Reload</button>
                        </td>
                    </tr>
                    <tr>
                        <td>Name:</td>
                        <td>
                            <input type="text" value={appState.name} onInput={e => appState.name = e.currentTarget.value} />
                            <input type="submit" />
                        </td>
                    </tr>
                </table>
            </form>
        }
    </fieldset>
})