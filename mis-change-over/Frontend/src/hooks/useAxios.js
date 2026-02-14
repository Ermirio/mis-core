import axios from 'axios';
import { jwtDecode } from 'jwt-decode';
import dayjs from 'dayjs';
import { useAuth } from '../context/AuthContext';

const baseURL = process.env.REACT_APP_SIDEBAR_API_BASE_URL || '/api';

const useAxios = () => {
    const { authTokens, setUser, setAuthTokens, logoutUser } = useAuth();

    const axiosInstance = axios.create({
        baseURL,
        xsrfCookieName: 'csrftoken',
        xsrfHeaderName: 'X-CSRFToken',
        headers: { Authorization: `Bearer ${authTokens?.access}` }
    });

    axiosInstance.interceptors.request.use(async req => {
        if (!authTokens) {
            return req;
        }

        const user = jwtDecode(authTokens.access);
        const isExpired = dayjs.unix(user.exp).diff(dayjs()) < 1;

        if (!isExpired) return req;

        try {
            const response = await axios.post(`${baseURL}/token/refresh/`, {
                refresh: authTokens.refresh
            });

            localStorage.setItem('authTokens', JSON.stringify(response.data));

            setAuthTokens(response.data);
            setUser(jwtDecode(response.data.access));

            req.headers.Authorization = `Bearer ${response.data.access}`;
            return req;
        } catch (error) {
            logoutUser();
            return Promise.reject(error);
        }
    });

    return axiosInstance;
};

export default useAxios;
