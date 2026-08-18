import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TaskProvider, useTasks } from './TaskContext'
import { useEffect } from 'react'

function TestComponent() {
  const { tasks, addTask, getLatestTask } = useTasks()

  return (
    <div>
      <div data-testid="task-count">{tasks.length}</div>
      <button
        onClick={() => {
          addTask('test_type', 'Test task label', async () => {
            return new Promise((resolve) => setTimeout(() => resolve({ success: true }), 100))
          })
        }}
      >
        Add Task
      </button>
      <div data-testid="tasks-list">
        {tasks.map(t => (
          <div key={t.id} data-testid={`task-${t.status}`}>
            {t.label} - {t.status}
          </div>
        ))}
      </div>
    </div>
  )
}

describe('TaskContext', () => {
  it('adds and completes a task', async () => {
    const user = userEvent.setup()
    
    render(
      <TaskProvider>
        <TestComponent />
      </TaskProvider>
    )

    // Initial state
    expect(screen.getByTestId('task-count')).toHaveTextContent('0')

    // Click to add task
    await user.click(screen.getByText('Add Task'))

    // Should immediately be running
    expect(screen.getByTestId('task-count')).toHaveTextContent('1')
    expect(screen.getByTestId('task-running')).toBeInTheDocument()

    // Wait for the async task to complete
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 150))
    })

    // Should now be done
    expect(screen.getByTestId('task-done')).toBeInTheDocument()
  })

  it('provides getLatestTask to restore state', async () => {
    let latestTask = null

    function ReaderComponent() {
      const { getLatestTask } = useTasks()
      useEffect(() => {
        latestTask = getLatestTask('test_type')
      })
      return null
    }

    const user = userEvent.setup()
    render(
      <TaskProvider>
        <TestComponent />
        <ReaderComponent />
      </TaskProvider>
    )

    await user.click(screen.getByText('Add Task'))
    
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 150))
    })

    expect(latestTask).not.toBeNull()
    expect(latestTask.status).toBe('done')
    expect(latestTask.result).toEqual({ success: true })
  })
})
