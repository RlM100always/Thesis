/** Research status — synthetic 32-shop storefront preview retired by request.
 * This is not the operational marketplace. Visit /stores to browse active
 * business-owned stores; the research and customer data are kept separate.
 */
import { useEffect, useState } from "react";
import { api } from "../api";

export default function ResearchPortal() {
  const [status, setStatus] = useState({loading:true,error:null,dataset:null});
  useEffect(() => {
    api.portalDatasets()
      .then(d => setStatus({loading:false,error:null,dataset:d.datasets?.[0] || null}))
      .catch(e => setStatus({loading:false,error:String(e),dataset:null}));
  }, []);
  return <main style={{maxWidth:760,padding:24,margin:"24px auto"}}>
    <h1>B-SMART Research Portal</h1>
    <p>পূর্বের ৩২টি কাল্পনিক দোকানের Explorer সরানো হয়েছে।
       এখানে operational দোকান বা customer order database দেখানো হয় না।</p>
    {status.loading ? <p>Research status loading…</p> : status.error ?
      <p role="alert">{status.error}</p> : <p>
      New research pipeline: <strong>{status.dataset?.status || "not ready"}</strong>.
      কোনো নতুন trained model বা validated research result এখনো প্রদর্শিত হচ্ছে না।
      </p>}
    <a href="#/stores">আসল Online Store Directory-তে যাও</a>
  </main>;
}
