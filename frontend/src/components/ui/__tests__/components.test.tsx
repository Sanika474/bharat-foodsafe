import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { Button } from '../Button';
import { Input } from '../Input';
import { Card } from '../Card';
import { Modal } from '../Modal';
import { Alert } from '../Alert';
import { Skeleton } from '../Skeleton';
import { EmptyState } from '../EmptyState';

describe('Button Component', () => {
  it('renders button text correctly', () => {
    render(<Button>Submit Check</Button>);
    expect(screen.getByRole('button', { name: 'Submit Check' })).toBeDefined();
  });

  it('renders primary variant by default', () => {
    const { container } = render(<Button>Primary</Button>);
    expect(container.firstElementChild?.className).toContain('bg-emerald-600');
  });

  it('renders danger variant', () => {
    const { container } = render(<Button variant="danger">Delete</Button>);
    expect(container.firstElementChild?.className).toContain('bg-red-600');
  });

  it('shows loading state and disables interaction', () => {
    render(<Button isLoading>Save</Button>);
    const button = screen.getByRole('button');
    expect(button.getAttribute('disabled')).not.toBeNull();
    expect(screen.getByText('Processing...')).toBeDefined();
  });

  it('triggers onClick callback when clicked', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click Me</Button>);
    fireEvent.click(screen.getByRole('button'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});

describe('Input Component', () => {
  it('renders label and binds htmlFor to input id', () => {
    render(<Input label="Temperature (°C)" id="temp-input" />);
    const label = screen.getByText('Temperature (°C)');
    expect(label.getAttribute('for')).toBe('temp-input');
    expect(screen.getByRole('textbox')).toBeDefined();
  });

  it('displays error message and sets aria-invalid', () => {
    render(<Input label="Temp" id="temp" error="Out of range threshold" />);
    const input = screen.getByRole('textbox');
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(screen.getByText('Out of range threshold')).toBeDefined();
  });

  it('displays helper text when no error exists', () => {
    render(<Input label="Unit" helperText="Enter Celsius unit" />);
    expect(screen.getByText('Enter Celsius unit')).toBeDefined();
  });

  it('handles user typing', () => {
    const handleChange = vi.fn();
    render(<Input label="Name" onChange={handleChange} />);
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'Walk-in Freezer' } });
    expect(handleChange).toHaveBeenCalled();
  });
});

describe('Card Component', () => {
  it('renders children content inside card container', () => {
    render(<Card><div>Card Body Content</div></Card>);
    expect(screen.getByText('Card Body Content')).toBeDefined();
  });

  it('applies interactive hover class when onClick is provided', () => {
    const handleClick = vi.fn();
    const { container } = render(<Card onClick={handleClick}>Clickable Card</Card>);
    expect(container.firstElementChild?.className).toContain('cursor-pointer');
    fireEvent.click(container.firstElementChild!);
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});

describe('Modal Component', () => {
  it('does not render content when isOpen is false', () => {
    render(<Modal isOpen={false} onClose={vi.fn()} title="Test Modal">Content</Modal>);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renders dialog and title when isOpen is true', () => {
    render(<Modal isOpen={true} onClose={vi.fn()} title="Configure Equipment">Modal Content</Modal>);
    expect(screen.getByRole('dialog')).toBeDefined();
    expect(screen.getByText('Configure Equipment')).toBeDefined();
    expect(screen.getByText('Modal Content')).toBeDefined();
  });

  it('calls onClose when close button is clicked', () => {
    const handleClose = vi.fn();
    render(<Modal isOpen={true} onClose={handleClose} title="Title">Content</Modal>);
    const closeBtn = screen.getByRole('button', { name: 'Close Modal' });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when Escape key is pressed', () => {
    const handleClose = vi.fn();
    render(<Modal isOpen={true} onClose={handleClose} title="Title">Content</Modal>);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});

describe('Alert Component', () => {
  it('renders title and message with success variant styling', () => {
    const { container } = render(
      <Alert variant="success" title="SOP Verified" message="Temperature logged successfully." />
    );
    expect(screen.getByText('SOP Verified')).toBeDefined();
    expect(screen.getByText('Temperature logged successfully.')).toBeDefined();
    expect(container.firstElementChild?.className).toContain('bg-emerald-50');
  });

  it('renders error variant styling and alert role', () => {
    const { container } = render(
      <Alert variant="error" title="Critical Deviation" message="Chiller temperature exceeded 8°C limit." />
    );
    expect(screen.getByRole('alert')).toBeDefined();
    expect(container.firstElementChild?.className).toContain('bg-red-50');
  });
});

describe('Skeleton Component', () => {
  it('renders pulsing element with aria-hidden true', () => {
    const { container } = render(<Skeleton className="w-24 h-6" />);
    const elem = container.firstElementChild;
    expect(elem?.className).toContain('animate-pulse');
    expect(elem?.className).toContain('w-24');
    expect(elem?.getAttribute('aria-hidden')).toBe('true');
  });
});

describe('EmptyState Component', () => {
  it('renders title and description', () => {
    render(
      <EmptyState
        title="No Tasks Assigned"
        description="All shift task checklists are completed."
      />
    );
    expect(screen.getByText('No Tasks Assigned')).toBeDefined();
    expect(screen.getByText('All shift task checklists are completed.')).toBeDefined();
  });

  it('renders action button and triggers callback when clicked', () => {
    const handleAction = vi.fn();
    render(
      <EmptyState
        title="No Incident Logs"
        description="Zero open incidents flagged for review."
        actionLabel="Refresh List"
        onAction={handleAction}
      />
    );
    const actionBtn = screen.getByRole('button', { name: 'Refresh List' });
    expect(actionBtn).toBeDefined();
    fireEvent.click(actionBtn);
    expect(handleAction).toHaveBeenCalledTimes(1);
  });
});
