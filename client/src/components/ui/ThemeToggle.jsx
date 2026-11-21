import { useTheme } from '../../theme/ThemeContext.jsx';
import { Icon } from './Icon.jsx';

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const next = theme === 'dark' ? 'light' : 'dark';
  return (
    <button className="btn btn-ghost press" onClick={toggle} aria-label={`Switch to ${next} mode`} title={`Switch to ${next} mode`}>
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
      <span style={{ fontSize: 12 }}>{theme === 'dark' ? 'Light' : 'Dark'}</span>
    </button>
  );
}
