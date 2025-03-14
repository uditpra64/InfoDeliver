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
  CircularProgress,
  Chip
} from '@mui/material';
import { useAppDispatch, useAppSelector } from '../../store/hooks/reduxHooks';
import { fetchAllFiles } from '../../store/slices/fileSlice';

const FileTable: React.FC = () => {
  const dispatch = useAppDispatch();
  const { files, loading, error } = useAppSelector(state => state.files);

  useEffect(() => {
    dispatch(fetchAllFiles());
  }, [dispatch]);

  if (loading) {
    return <CircularProgress />;
  }

  if (error) {
    return <Typography color="error">{error}</Typography>;
  }

  return (
    <>
      <Typography variant="h6" component="h2" gutterBottom>
        ファイル一覧
      </Typography>
      <TableContainer component={Paper}>
        <Table size="small" aria-label="file table">
          <TableHead>
            <TableRow>
              <TableCell>ファイル名</TableCell>
              <TableCell>タスク</TableCell>
              <TableCell>アップロード日時</TableCell>
              <TableCell>行数</TableCell>
              <TableCell>出力用</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {files.map((file) => (
              <TableRow key={file.id}>
                <TableCell>{file.name}</TableCell>
                <TableCell>{file.task_name}</TableCell>
                <TableCell>{file.upload_date}</TableCell>
                <TableCell>{file.row_count}</TableCell>
                <TableCell>
                  {file.output ? (
                    <Chip label="出力用" color="primary" size="small" />
                  ) : (
                    <Chip label="入力用" size="small" />
                  )}
                </TableCell>
              </TableRow>
            ))}
            {files.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} align="center">
                  ファイルがありません
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
};

export default FileTable;