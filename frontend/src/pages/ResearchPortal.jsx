/** New research portal — previous datasets/models are deliberately absent. */
import { useEffect, useState } from "react";
import { api } from "../api";

export default function ResearchPortal() {
  const [data, setData] = useState({loading:true, dataset:null, storage:null, error:null});
  useEffect(() => {
    Promise.all([api.portalDatasets(), api.portalStorage()])
      .then(([d,s])=>setData({loading:false,dataset:d.datasets?.[0]||null,storage:s,error:null}))
      .catch(e=>setData({loading:false,dataset:null,storage:null,error:String(e)}));
  },[]);
  return (
    <main style={{maxWidth:900,margin:"28px auto",padding:24}}>
      <h1>B-SMART Research Portal</h1>
      <p>Fresh start: old trained models and experimental results have been retired.</p>
      {data.loading ? <p>Loading status…</p> : data.error ? <p role="alert">{data.error}</p> :
        <section className="card" style={{padding:20}}>
          <h2>{data.dataset?.name || "New dataset"}</h2>
          <p>Evidence: <strong>synthetic Bangladesh-context SME</strong> (not observed business records).</p>
          <p>Data: <strong>{data.dataset?.installed ? "Installed" : "Awaiting import"}</strong></p>
          <p>Models: <strong>Untrained after reset</strong></p>
          <p>Persistent R2: {data.storage?.r2_configured ? "Configured" : "Not configured"}</p>
        </section>
      }
      <p>New RQ1–RQ4 experiments will only be shown after validated data import and rerun.</p>
      <a href="https://github.com/RlM100always/Thesis/blob/main/docs/NEW_DATASET_REBUILD.md"
        target="_blank" rel="noreferrer">Read research rebuilding plan</a>
    </main>
  );
}
