export function createLogger(scope) {
  const stamp = () => new Date().toISOString().slice(11, 19);
  return {
    info: (...a) => console.log(stamp(), 'INFO ', `[${scope}]`, ...a),
    warn: (...a) => console.warn(stamp(), 'WARN ', `[${scope}]`, ...a),
    error: (...a) => console.error(stamp(), 'ERROR', `[${scope}]`, ...a),
  };
}
