import axios from 'axios';

async function test() {
  try {
    const response = await axios.post('http://127.0.0.1:8000/query', {
      query: 'USA',
      top_k: 10,
      rerank_top_k: 5
    });
    console.log("Success:", response.data);
  } catch (err) {
    console.error("Axios Error:", err.message);
    if (err.response) {
      console.error("Response data:", err.response.data);
    }
  }
}
test();
