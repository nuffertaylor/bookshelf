const http_result = (status_code, body) => {
  return {statusCode : status_code, body : body};
}

export const login = () => {

};

export const register = (username, password, email) => {
  //handle missing data
  if(!username) return http_result(403, "invalid input, missing username");
  if(!password) return http_result(403, "invalid input, missing password");
  if(!email) return http_result(403, "invalid input, missing email");

  
};

