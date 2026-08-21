from datetime import datetime
import logging

logger = logging.getLogger('CommandQueue')

# Simple In-Memory Queue
# Structure: line_id -> [ { 'id': '...', 'timestamp': '...', 'commands': [...] } ]
_queue = {}

def add_command(line_id, command_batch):
    """
    Adds a batch of commands to the queue for a specific line.
    command_batch: { 'id': str, 'commands': list, 'source': str }
    """
    if line_id not in _queue:
        _queue[line_id] = []
    
    # Add timestamp
    command_batch['timestamp'] = datetime.utcnow().isoformat()
    _queue[line_id].append(command_batch)
    
    # Initialize Status immediately to avoid race condition
    _status[command_batch['id']] = {
        'status': 'QUEUED',
        'message': 'Na fila de envio...',
        'progress': {'current': 0, 'total': len(command_batch['commands'])},
        'updated_at': datetime.utcnow().isoformat()
    }
    
    logger.info(f"Queued {len(command_batch['commands'])} commands for Line {line_id}")

def get_pending_commands(line_id=None):
    """
    Retrieves and removes pending commands.
    If line_id is provided, returns commands for that line.
    If line_id is None, returns ALL commands (flat list of batches).
    
    WARNING: This consumes the commands!
    """
    results = []
    
    if line_id:
        if line_id in _queue and _queue[line_id]:
            results = _queue[line_id]
            _queue[line_id] = [] # Clear queue
    else:
        # Get all
        for lid in list(_queue.keys()):
            if _queue[lid]:
                results.extend(_queue[lid])
                _queue[lid] = []
                
    return results

# Status Store: batch_id -> { status: 'PENDING'|'SUCCESS'|'ERROR', message: '...', progress: { current: 0, total: 0 } }
_status = {}

def update_command_status(batch_id, status, message, progress=None):
    entry = _status.get(batch_id, {})
    entry.update({
        'status': status, 
        'message': message, 
        'updated_at': datetime.utcnow().isoformat()
    })
    if progress:
        entry['progress'] = progress
    _status[batch_id] = entry
    # logger.info(f"Batch {batch_id} status updated to {status}") # Reduce log noise for progress

def get_command_status(batch_id):
    return _status.get(batch_id, {'status': 'UNKNOWN', 'message': 'Batch not found'})

def peek_queue():
    """Debug utility to see queue without consuming."""
    return _queue
