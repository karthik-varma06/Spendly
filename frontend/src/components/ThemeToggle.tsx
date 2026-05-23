import { MoonStar, SunMedium } from 'lucide-react';
import Button from './ui/Button';
import { useTheme } from '../context/ThemeContext';

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <Button variant="ghost" onClick={toggleTheme} className="h-11 px-3">
      {theme === 'dark' ? <SunMedium className="h-4 w-4" /> : <MoonStar className="h-4 w-4" />}
      <span>{theme === 'dark' ? 'Light' : 'Dark'}</span>
    </Button>
  );
}