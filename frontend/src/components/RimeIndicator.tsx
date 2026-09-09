export function RimeIndicator() {
  return (
    <div className="provider-indicator" aria-label="Rime voice provider, Coda model, Lyra speaker">
      <span className="provider-pulse" aria-hidden="true" />
      <span>
        <small>VOICE ENGINE</small>
        <strong>Rime <i>Coda · Lyra</i></strong>
      </span>
    </div>
  );
}
