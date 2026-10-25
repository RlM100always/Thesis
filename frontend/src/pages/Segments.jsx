/** Old research results retired. Do not display archived metrics as new claims. */
export default function Segments() {
  return (
    <main style={{maxWidth:760, margin:"32px auto", padding:24}}>
      <h1>B-SMART Research Reset</h1>
      <p>Earlier datasets and trained models have been removed from the main branch.</p>
      <p>The new Bangladesh-context SME integrated dataset is <strong>100% synthetic</strong>
       and is awaiting import. There are no new verified model results on this page.</p>
      <p><a href="https://github.com/RlM100always/Thesis/blob/main/docs/NEW_DATASET_REBUILD.md"
        target="_blank" rel="noreferrer">View research rebuilding plan</a></p>
    </main>
  );
}
