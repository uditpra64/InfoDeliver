import React, { useEffect } from 'react';
import { 
  Typography, 
  Paper, 
  Table, 
  TableBody, 
  TableCell, 
  TableContainer, 
  TableHead, 
  TableRow,
  CircularProgress
} from '@mui/material';
import { useAppDispatch, useAppSelector } from '../../store/hooks/reduxHooks';
import { fetchAllTasks, selectTask } from '../../store/slices/taskSlice';

const TaskTable: React.FC = () => {
  const dispatch = useAppDispatch();
  const { tasks, loading, error, selectedTaskId } = useAppSelector(state => state.tasks);

  useEffect(() => {
    dispatch(fetchAllTasks());
  }, [dispatch]);

  const handleTaskClick = (taskId: string) => {
    console.log(`Selecting task: ${taskId}`);
    dispatch(selectTask(taskId));
  };

  if (loading) {
    return <CircularProgress />;
  }

  if (error) {
    return <Typography color="error">{error}</Typography>;
  }

  return (
    <>
      <Typography variant="h6" component="h2" gutterBottom>
        タスク一覧
      </Typography>
      <TableContainer component={Paper}>
        <Table size="small" aria-label="task table">
          <TableHead>
            <TableRow>
              <TableCell>名称</TableCell>
              <TableCell>概要</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {tasks.map((task) => (
              <TableRow 
                key={task.task_id}
                onClick={() => handleTaskClick(task.task_id)}
                hover
                selected={task.task_id === selectedTaskId}
                sx={{ 
                  cursor: 'pointer',
                  '&:hover': { backgroundColor: 'rgba(0, 0, 0, 0.04)' },
                  backgroundColor: task.task_id === selectedTaskId ? 'rgba(25, 118, 210, 0.12)' : 'inherit'
                }}
              >
                <TableCell>{task.name}</TableCell>
                <TableCell>{task.description}</TableCell>
              </TableRow>
            ))}
            {tasks.length === 0 && (
              <TableRow>
                <TableCell colSpan={2} align="center">
                  タスクがありません
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
};

export default TaskTable;